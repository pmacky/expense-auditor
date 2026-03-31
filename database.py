

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ─────────────────────────────────────────
# TABLE 1: Users
# Stores everyone who can log into the app
# ─────────────────────────────────────────
class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(100), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(20), nullable=False)  # 'employee' or 'finance'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    def __repr__(self):
        return f'<User {self.email}>'


# ─────────────────────────────────────────
# TABLE 2: Claims
# Stores every expense claim submitted
# ─────────────────────────────────────────
class Claim(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    employee_name    = db.Column(db.String(100), nullable=False)
    employee_email   = db.Column(db.String(100), nullable=False)

    # Receipt details
    merchant         = db.Column(db.String(200))
    amount           = db.Column(db.String(50))
    date             = db.Column(db.String(50))
    category         = db.Column(db.String(50))
    business_purpose = db.Column(db.Text)
    file_path        = db.Column(db.String(300))
    claimed_date     = db.Column(db.String(50))

    # AI Audit results
    status           = db.Column(db.String(20))   
    reason           = db.Column(db.Text)
    risk_score       = db.Column(db.Integer)       
    policy_snippet   = db.Column(db.Text)          
    # Finance team override
    override_status  = db.Column(db.String(20))   
    override_comment = db.Column(db.Text)          
    overridden_by    = db.Column(db.String(100))   

    # Timestamps
    submitted_at     = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at      = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Claim {self.id} - {self.status}>'
# ─────────────────────────────────────────
# TABLE 3: Notifications
# Stores alerts for employees
# ─────────────────────────────────────────
class Notification(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id}>'
    @property
    def final_status(self):
        return self.override_status if self.override_status else self.status