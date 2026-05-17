# 🎯 AtomQuest Goals Portal

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-purple.svg)

A complete Goal Setting & Tracking Portal built for the AtomQuest Hackathon 1.0.

**Live Demo:** [https://nnui7890.pythonanywhere.com](https://nnui7890.pythonanywhere.com)

---

## 📑 Table of Contents
- [Tech Stack](#-tech-stack)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Demo Credentials](#-demo-credentials)
- [Project Structure](#-project-structure)
- [Cost Optimisation Notes](#-cost-optimisation-notes)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0 |
| Templates | Jinja2 |
| Styling | Bootstrap 5 (CDN) + Custom CSS |
| Database | SQLite → PostgreSQL ready |
| Auth | Flask-Login (session-based) |
| Forms | Flask-WTF |
| Charts | Chart.js (CDN) |
| Export | pandas + openpyxl |
| Hosting | PythonAnywhere |

## ✨ Features

### Phase 1 — Goal Creation & Approval (Must-Have)
- Employee creates goals with Thrust Area, UoM, Target, Weightage
- Validation: Total weightage = 100%, Min 10% per goal, Max 8 goals
- Manager reviews, approves, or returns with comments
- Admin can unlock locked goals with audit trail

### Phase 2 — Achievement Tracking & Check-ins (Must-Have)
- Quarterly check-ins (Q1–Q4)
- Auto-calculated scores based on UoM type (Min/Max/Timeline/Zero)
- Manager check-in comments
- Status tracking: Not Started / On Track / Completed

### Bonus Features Implemented

#### 1. Escalation Module (Rule-Based)
- **Draft goal warning**: Employee hasn't submitted goals within 7 days
- **Pending approval warning**: Manager hasn't approved goals within 5 days
- **Missing check-in warning**: Quarterly check-in not completed in active window
- Visual alert banner on Admin Dashboard with action buttons

#### 2. Analytics Module
- **Goal Distribution Charts**: Pie charts showing goals by Thrust Area and UoM type
- **Manager Effectiveness Leaderboard**: Ranked table with completion rates, progress bars, and trophy badges for top 3

#### 3. Simulated Email Notifications
- Flash messages simulate email delivery on key actions:
  - Goal submitted → Manager notified
  - Goal approved/returned → Employee notified
  - Check-in completed → Manager notified
  - Manager comment added → Employee notified

#### 4. Audit Log Export
- Export full audit trail to CSV from Admin Dashboard

### Reporting & Governance
- Export all goals to Excel
- Admin dashboard with completion donut chart + distribution analytics
- Real-time status overview
- Audit log for all unlock actions

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/atomquest.git
cd atomquest
```

### 2. Set up Virtual Environment
**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Locally
```bash
python app.py
```
App starts at `http://localhost:5000`

---

## 🔑 Demo Credentials

Visit [https://nnui7890.pythonanywhere.com](https://nnui7890.pythonanywhere.com) and use any of the demo credentials below.

| Role | Email | Password | Notes |
|------|-------|----------|-------|
| Admin | admin@atomquest.com | admin123 | Full dashboard access |
| Manager | alex@atomquest.com | alex123 | Engineering Lead — 2 team members |
| Manager | lisa@atomquest.com | lisa123 | Sales Director — 2 team members |
| Manager | david@atomquest.com | david123 | Operations Head — 2 team members |
| Employee | employee@atomquest.com | employee123 | Under Alex — all approved |
| Employee | sarah@atomquest.com | sarah123 | Under Alex — has returned goal |
| Employee | mike@atomquest.com | mike123 | Under Lisa — high performer |
| Employee | emma@atomquest.com | emma123 | Under Lisa — draft goals |
| Employee | james@atomquest.com | james123 | Under David — solid performer |
| Employee | priya@atomquest.com | priya123 | Under David — pending review |

### Demo Data Scenarios

| Employee | Manager | Status | Escalation Trigger |
|----------|---------|--------|-------------------|
| Employee User | Alex | All approved, 100% check-ins | None |
| Sarah Chen | Alex | 3 approved + 1 returned goal | Draft goal 7+ days old |
| Mike Ross | Lisa | All approved, 100% check-ins | None |
| Emma Wilson | Lisa | 2 approved + 2 draft goals | Draft goals not submitted |
| James Lee | David | All approved, 100% check-ins | None |
| Priya Sharma | David | 1 approved + 3 submitted | Pending approval 5+ days |

---

## 📁 Project Structure

```text
atomquest/
├── app.py              # Main Flask app (routes, models, forms, analytics)
├── requirements.txt    # Python dependencies
├── wsgi.py             # WSGI entry for PythonAnywhere
├── goals.db            # SQLite database (auto-created)
├── static/
│   └── style.css       # Custom stylesheet
└── templates/
    ├── base.html       # Layout template
    ├── login.html      # Login page with demo credentials selector
    ├── dashboard.html  # Admin dashboard + analytics + escalation alerts
    ├── goals.html      # Employee goals
    ├── team.html       # Manager team view
    ├── approve.html    # Manager approval
    ├── checkin.html    # Employee check-in
    └── checkin_view.html # Manager check-in view
```

### URL Structure

| Route | Role | Description |
|-------|------|-------------|
| `/login` | All | Sign in with demo credentials selector |
| `/employee/goals` | Employee | Create & manage goals |
| `/employee/checkin` | Employee | Quarterly check-ins |
| `/manager/team` | Manager | Team overview with pending badges |
| `/manager/approve/<id>` | Manager | Review & approve/return goals |
| `/manager/checkin/<id>` | Manager | View team check-ins & add comments |
| `/admin/dashboard` | Admin | Dashboard + analytics + escalation alerts |
| `/export/goals` | Manager/Admin | Download Excel report |
| `/export/audit` | Admin | Download audit CSV |

---

## 🗄️ Database Migration (PostgreSQL)

Change in `app.py`:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@host/dbname'
```
Everything else stays the same — SQLAlchemy handles the rest.

---

## 💡 Cost Optimisation Notes

- **Zero external API dependencies** — no API keys, rate limits, or vendor costs
- **SQLite file-based database** — zero hosting cost for database
- **CDN assets only** — Bootstrap, Chart.js, Fonts loaded via CDN (no build pipeline)
- **Session-based auth** — no OAuth/SAML complexity or costs
- **In-memory exports** — Excel/CSV generated on-demand, no storage costs
- **Single lightweight Flask process** — scales vertically on basic hosting

---

## 📜 License

Built for AtomQuest Hackathon 1.0
