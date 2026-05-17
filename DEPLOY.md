# AtomQuest — PythonAnywhere Deployment Guide

## Step 1: Upload Files

1. Go to **Files** tab in PythonAnywhere
2. Create folder: `atomquest/`
3. Upload all files:
   - `app.py`
   - `requirements.txt`
   - `wsgi.py` (updated with your username)
   - `static/style.css`
   - `templates/*.html`

## Step 2: Create Virtual Environment

Open a **Bash console** and run:

```bash
cd ~/atomquest
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 3: Configure WSGI

Edit `wsgi.py`:

```python
import sys
import os

path = '/home/YOUR_USERNAME/atomquest'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import app as application
```

Replace `YOUR_USERNAME` with your actual PythonAnywhere username.

## Step 4: Web App Config

1. Go to **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration** → **Python 3.10**
4. Set:
   - **Source code**: `/home/YOUR_USERNAME/atomquest`
   - **Working directory**: `/home/YOUR_USERNAME/atomquest`
   - **WSGI configuration file**: `/home/YOUR_USERNAME/atomquest/wsgi.py`
   - **Virtualenv**: `/home/YOUR_USERNAME/atomquest/venv`

## Step 5: Static Files

In the **Web** tab, add:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOUR_USERNAME/atomquest/static` |

## Step 6: Reload

Click the **Reload** button. Your app is live!

## URL Structure

| Route | Role | Description |
|-------|------|-------------|
| `/login` | All | Sign in |
| `/employee/goals` | Employee | Create & manage goals |
| `/employee/checkin` | Employee | Quarterly check-ins |
| `/manager/team` | Manager | Team overview |
| `/manager/approve/<id>` | Manager | Review & approve goals |
| `/manager/checkin/<id>` | Manager | View team check-ins |
| `/admin/dashboard` | Admin | Dashboard & audit |
| `/export/goals` | Manager/Admin | Download Excel |

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@atomquest.com | admin123 |
| Manager | manager@atomquest.com | manager123 |
| Employee | employee@atomquest.com | employee123 |

## Troubleshooting

### Database not found
Make sure SQLite path is absolute in `app.py`:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'goals.db')
```

### Static files not loading
Check the static files mapping in the Web tab.

### Import errors
Make sure virtualenv is activated and all packages installed:
```bash
source venv/bin/activate
pip list
```
