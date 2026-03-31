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
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

load_dotenv()

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

@app.route('/')
@login_required
def home():
    claims = Claim.query.filter_by(employee_id=current_user.id)\
                        .order_by(Claim.submitted_at.desc()).all()
    return render_template('employee.html', claims=claims)


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

    icon = '✅' if result['status'] == 'Approved' else '⚠️' if result['status'] == 'Flagged' else '❌'
    notification = Notification(
        user_id = current_user.id,
        message = f"{icon} Your claim at {result['merchant']} for {result['amount']} was {result['status']} by AI. {result['reason']}"
    )
    db.session.add(notification)
    db.session.commit()
    print(f"✅ Notification created for user {current_user.id}: {notification.message}")

    return jsonify(result)
# ─────────────────────────────────────────
# FINANCE ROUTES
# ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'finance':
        return redirect(url_for('home'))

    claims = Claim.query.order_by(Claim.risk_score.desc()).all()
    return render_template('dashboard.html', claims=claims)


@app.route('/claim/<int:claim_id>')
@login_required
def claim_detail(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    return render_template('detail.html', claim=claim)


@app.route('/override/<int:claim_id>', methods=['POST'])
@login_required
def override_claim(claim_id):
    if current_user.role != 'finance':
        return jsonify({'error': 'Unauthorized'}), 403

    claim                  = Claim.query.get_or_404(claim_id)
    new_status             = request.form['status']
    comment                = request.form['comment']
    claim.override_status  = new_status
    claim.override_comment = comment
    claim.overridden_by    = current_user.name
    db.session.commit()

    icon = '✅' if new_status == 'Approved' else '⚠️' if new_status == 'Flagged' else '❌'
    notification = Notification(
        user_id = claim.employee_id,
        message = f"{icon} Your claim at {claim.merchant or 'Unknown'} for {claim.amount or '?'} was {new_status} by Finance. Note: {comment}"
    )
    db.session.add(notification)
    db.session.commit()

    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/api/claims')
@login_required
def get_claims():
    claims = Claim.query.all()
    return jsonify([{
        'id':       c.id,
        'employee': c.employee_name,
        'status':   c.final_status,
        'amount':   c.amount,
        'category': c.category,
        'risk':     c.risk_score
    } for c in claims])


from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

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