from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from database import db, User, Claim
from auditor import run_audit_pipeline
from database import db, User, Claim, Notification
import os
import re
import fitz
import pytesseract

# Force Railway path
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

app = Flask(__name__)

app.config['SECRET_KEY']           = 'supersecretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'strong'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email='finance@company.com').first():
        finance_user = User(
            name     = 'Finance Team',
            email    = 'finance@company.com',
            password = generate_password_hash('finance123'),
            role     = 'finance'
        )
        db.session.add(finance_user)
        db.session.commit()
        print("✅ Default finance user created: finance@company.com / finance123")


# ─────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'finance':
                return redirect(url_for('dashboard'))
            return redirect(url_for('home'))

        flash('Invalid email or password')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))

        user = User(
            name     = name,
            email    = email,
            password = generate_password_hash(password),
            role     = 'employee'
        )
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─────────────────────────────────────────
# EMPLOYEE ROUTES
# ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'finance':
        return redirect(url_for('home'))
    claims = Claim.query.order_by(Claim.risk_score.desc()).all()
    from flask import make_response
    response = make_response(render_template('dashboard.html', claims=claims))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.route('/submit', methods=['POST'])
@login_required
def submit_claim():
    file             = request.files['receipt']
    business_purpose = request.form['business_purpose']
    claimed_date     = request.form['claimed_date']

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        receipt_text = ""
        doc = fitz.open(filepath)
        for page in doc:
            receipt_text += page.get_text()
    else:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(filepath)

        # Convert to grayscale
        img = img.convert('L')

        # Increase size for better OCR
        width, height = img.size
        img = img.resize((width * 3, height * 3), Image.LANCZOS)

        # Sharpen twice
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)

        # Boost contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(3.0)

        # Boost brightness
        brightness = ImageEnhance.Brightness(img)
        img = brightness.enhance(1.5)

        # Try multiple OCR modes
        text1 = pytesseract.image_to_string(img, config='--psm 6')
        text2 = pytesseract.image_to_string(img, config='--psm 4')
        text3 = pytesseract.image_to_string(img, config='--psm 11')

        # Use whichever mode got the most text
        receipt_text = max([text1, text2, text3], key=len)

        print("=== OCR OUTPUT ===")
        print(receipt_text)
        print("==================")

        # ── Blurry receipt checks ──────────────────────
        clean_text    = receipt_text.strip().replace('\n','').replace(' ','')
        numbers_found = re.findall(r'\d+\.?\d*', receipt_text)
        words         = [w for w in receipt_text.split() if len(w) > 2]

        if len(clean_text) < 20:
            return jsonify({
                "error": "blurry",
                "message": "Receipt image is too blurry or unclear to read. Please upload a clearer photo or use a PDF instead."
            }), 400

        if len(numbers_found) == 0:
            return jsonify({
                "error": "blurry",
                "message": "Could not detect any amounts in this image. Make sure the receipt is well lit and in focus."
            }), 400

        if len(words) < 5:
            return jsonify({
                "error": "blurry",
                "message": "Receipt appears too blurry. Try better lighting or upload a PDF."
            }), 400
        # ───────────────────────────────────────────────

    policy_text = ""
    if os.path.exists("policy.pdf"):
        policy_doc = fitz.open("policy.pdf")
        for page in policy_doc:
            policy_text += page.get_text()
    else:
        policy_text = "Standard expense policy: Meals up to $50, Transport up to $100, Lodging up to $200 per night. No alcohol reimbursement."

    result = run_audit_pipeline(receipt_text, business_purpose, policy_text, claimed_date)

    claim = Claim(
        employee_id      = current_user.id,
        claimed_date     = claimed_date,
        employee_name    = current_user.name,
        employee_email   = current_user.email,
        merchant         = result['merchant'],
        amount           = result['amount'],
        date             = result['date'],
        category         = result['category'],
        business_purpose = business_purpose,
        file_path        = filepath,
        status           = result['status'],
        reason           = result['reason'],
        risk_score       = result['risk_score'],
        policy_snippet   = result['policy_snippet']
    )
    db.session.add(claim)
    db.session.commit()

    # Notify employee of initial audit result
    status = result['status']
    icon = '[APPROVED]' if status == 'Approved' else '[FLAGGED]' if status == 'Flagged' else '[REJECTED]'
    notification = Notification(
        user_id = claim.employee_id,
        message = f"{icon} Your claim at {claim.merchant or 'Unknown'} ({claim.amount or '?'}) was {status}. Reason: {result['reason']}"
    )
    db.session.add(notification)
    db.session.commit()
    return jsonify(result)
# ─────────────────────────────────────────
# FINANCE ROUTES
# ─────────────────────────────────────────

@app.route('/')
@login_required
def home():
    # Force fresh data from database
    db.session.expire_all()
    claims = Claim.query.filter_by(employee_id=current_user.id)\
                        .order_by(Claim.submitted_at.desc()).all()
    from flask import make_response
    response = make_response(render_template('employee.html', claims=claims))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/claim/<int:claim_id>')
@login_required
def claim_detail(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    return render_template('detail.html', claim=claim)


@app.route('/override/<int:claim_id>', methods=['POST'])
@login_required
def override_claim(claim_id):
    # Re-fetch current user from DB to avoid stale session
    fresh_user = db.session.get(User, current_user.id)

    if fresh_user.role != 'finance':
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.expire_all()
    claim = db.session.get(Claim, claim_id)
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404

    new_status             = request.form['status']
    comment                = request.form['comment']
    claim.override_status  = new_status
    claim.override_comment = comment
    claim.overridden_by    = fresh_user.name

    if new_status == 'Approved':
        status_icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0ecb81" stroke-width="2.5" stroke-linecap="round" style="vertical-align:middle;margin-right:6px"><polyline points="20 6 9 17 4 12"/></svg>'
    elif new_status == 'Flagged':
        status_icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f7a600" stroke-width="2.5" stroke-linecap="round" style="vertical-align:middle;margin-right:6px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    else:
        status_icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f6465d" stroke-width="2.5" stroke-linecap="round" style="vertical-align:middle;margin-right:6px"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'

    notification = Notification(
        user_id = claim.employee_id,
        message = f"{status_icon} Finance overrode your claim at {claim.merchant or 'Unknown'} ({claim.amount or '?'}) to <strong>{new_status}</strong>. Note: {comment}"
    )
    db.session.add(notification)
    db.session.commit()

    print(f"✅ Override saved: claim {claim_id} → {new_status}")
    return redirect(url_for('claim_detail', claim_id=claim_id))

@app.route('/api/claims')
@login_required
def get_claims():
    db.session.expire_all()
    claims = Claim.query.order_by(Claim.risk_score.desc()).all()
    return jsonify([{
        'id':       c.id,
        'employee': c.employee_name,
        'merchant': c.merchant or '—',
        'amount':   c.amount or '—',
        'category': c.category or '—',
        'status':   c.final_status,
        'risk':     c.risk_score
    } for c in claims])

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(os.path.abspath(UPLOAD_FOLDER), filename)

# ─────────────────────────────────────────
# NOTIFICATION ROUTES
# ─────────────────────────────────────────

@app.route('/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()

    return jsonify([{
        'id':      n.id,
        'message': n.message,
        'time':    n.created_at.strftime('%d %b, %H:%M')
    } for n in notifications])


@app.route('/notifications/read', methods=['POST'])
@login_required
def mark_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})   

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')