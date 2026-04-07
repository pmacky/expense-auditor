# 💼 ExpenseAI — AI-Powered Expense Auditor

A policy-first corporate expense auditing system that uses a 
multi-agent AI pipeline to automatically audit receipts against 
company policy in real time.

Built with Python, Flask, and Groq AI.

---

## 📌 Project Title
ExpenseAI — AI-Powered Expense Auditor

---

## ❗ The Problem
Corporate expense auditing is a manual, time-consuming process where finance teams must verify receipts against complex company policies. This leads to delays, human errors, and financial leakage due to non-compliant claims slipping through.

---

## 💡 The Solution
ExpenseAI automates the auditing process using a multi-agent AI pipeline. It extracts data from receipts using OCR, cross-references it with company policies, and evaluates compliance in real time. The system classifies claims as Approved, Flagged, or Rejected, generates explanations, and assigns fraud risk scores, reducing manual effort and improving accuracy.

---

## 🚀 Features

- **4-Agent AI Pipeline** — Four specialized AI agents work in sequence to extract, search, audit and score every claim
- **OCR Receipt Reading** — Automatically extracts merchant, amount, date and category from receipt images and PDFs
- **Policy Cross-Reference** — Reads a 40-page company policy PDF and finds relevant rules for each expense
- **Fraud Risk Scoring** — Every claim gets a 0-100 fraud risk score based on suspicious patterns
- **Traffic Light System** — Claims are categorized as Approved, Flagged, or Rejected with a one-sentence explanation
- **Finance Dashboard** — All claims sorted by risk level so Finance can focus on high-risk items first
- **Human Override** — Finance team can override AI decisions with a custom comment
- **Real-time Notifications** — Bell icon alerts employees when their claim is reviewed
- **Date Validation** — Flags claims where receipt date doesn't match submission date
- **Blurry Receipt Detection** — Detects unreadable receipt images and asks for a clearer photo
- **Role-based Login** — Separate portals for employees and finance team
- **Mobile Friendly** — Fully responsive on all screen sizes

---

## 🤖 How the AI Pipeline Works

~~~text
Receipt uploaded
      ↓
Agent 1 (Groq/LLaMA) — Extracts structured data from receipt
      ↓
Agent 2 (Groq/LLaMA) — Searches policy PDF for relevant rules
      ↓
Agent 3 (Groq/LLaMA) — Audits claim against policy rules
      ↓
Agent 4 (Groq/LLaMA) — Calculates fraud risk score 0-100
      ↓
Result saved to database + employee notified
~~~

---

## 🛠️ Tech Stack

- **Programming Languages:** Python, JavaScript, HTML, CSS  
- **Frameworks:** Flask, SQLAlchemy, Flask-Login  
- **Database:** SQLite  
- **APIs / Tools:**  
  - Groq API (LLaMA 3.3 70B)  
  - Tesseract OCR (pytesseract)  
  - Pillow  
  - PyMuPDF  

---

## 🌐 Live Demo

🚀 **Try it live:**  
https://expense-auditor-production.up.railway.app/login?next=%2F

---

## ⚙️ Setup Instructions

### 1. Clone the repository

~~~bash
git clone https://github.com/YOUR_USERNAME/expense-auditor.git
cd expense-auditor
~~~

### 2. Create virtual environment

~~~bash
python -m venv venv
venv\Scripts\activate.bat   # Windows
source venv/bin/activate    # Mac/Linux
~~~

### 3. Install dependencies

~~~bash
python -m pip install flask flask-sqlalchemy flask-login flask-mail werkzeug anthropic groq python-dotenv pillow pytesseract PyMuPDF
~~~

### 4. Install Tesseract OCR

Download from:  
https://github.com/UB-Mannheim/tesseract/wiki

Update path in `app.py`:

~~~python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
~~~

### 5. Set up environment variables

Create a `.env` file:

~~~env
ANTHROPIC_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
~~~

### 6. Add your policy PDF

Place your company's expense policy PDF in the root folder named `policy.pdf`.

### 7. Run the app

~~~bash
python app.py
~~~

Visit `http://127.0.0.1:5000`

---

## 👤 Default Accounts

| Role | Email | Password |
|---|---|---|
| Finance Team | finance@company.com | finance123 |
| Employee | Register at /register | Your choice |

---

## 📁 Project Structure

~~~text
expense-auditor/
│
├── app.py          ← Main Flask server + routes
├── database.py     ← SQLAlchemy models (User, Claim, Notification)
├── auditor.py      ← 4-agent AI pipeline
├── policy.pdf      ← Company expense policy
├── .env            ← API keys (never commit this)
│
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── employee.html
│   ├── dashboard.html
│   └── detail.html
│
└── uploads/        ← Saved receipt files
~~~

---

## 📄 License

MIT License — free to use and modify.
