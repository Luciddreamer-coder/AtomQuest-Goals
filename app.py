from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FloatField, SubmitField, PasswordField
from wtforms.validators import DataRequired, NumberRange, ValidationError
from functools import wraps
from datetime import datetime, timedelta
import os
import pandas as pd
from io import BytesIO, StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'atomquest-hackathon-2025-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'goals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access this page.'
login_manager.login_message_category = 'warning'

# ============================================
# JINJA2 CONTEXT PROCESSOR (CSRF TOKEN)
# ============================================

from flask_wtf.csrf import generate_csrf

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)


# ============================================
# MODELS
# ============================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # employee, manager, admin
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    department = db.Column(db.String(100), nullable=True)

    # Relationships
    goals = db.relationship('Goal', backref='owner', lazy=True, foreign_keys='Goal.user_id')
    team_members = db.relationship('User', backref=db.backref('manager', remote_side=[id]), lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

class Goal(db.Model):
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    thrust_area = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    uom = db.Column(db.String(50), nullable=False)  # numeric_min, numeric_max, percentage_min, percentage_max, timeline, zero
    target = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, submitted, approved, returned
    is_locked = db.Column(db.Boolean, default=False)
    is_shared = db.Column(db.Boolean, default=False)
    shared_goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=True)
    manager_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    checkins = db.relationship('CheckIn', backref='goal', lazy=True, cascade='all, delete-orphan')

class CheckIn(db.Model):
    __tablename__ = 'checkins'
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    quarter = db.Column(db.String(10), nullable=False)  # Q1, Q2, Q3, Q4
    planned = db.Column(db.Float, nullable=True)
    actual = db.Column(db.Float, nullable=True)
    score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='not_started')  # not_started, on_track, completed
    manager_comment = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AppConfig(db.Model):
    __tablename__ = 'app_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

# ============================================
# USER LOADER
# ============================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================
# ROLE DECORATORS
# ============================================

def employee_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'employee':
            flash('Access denied. Employee role required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'manager':
            flash('Access denied. Manager role required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied. Admin role required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_cycle_status():
    config = AppConfig.query.filter_by(key='cycle_open').first()
    return config.value == 'true' if config else False

def set_cycle_status(status):
    config = AppConfig.query.filter_by(key='cycle_open').first()
    if not config:
        config = AppConfig(key='cycle_open', value='false')
        db.session.add(config)
    config.value = 'true' if status else 'false'
    db.session.commit()

def log_audit(action, target_type=None, target_id=None, reason=None):
    log = AuditLog(
        user_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason
    )
    db.session.add(log)
    db.session.commit()

def calculate_score(goal, actual):
    """Calculate progress score based on UoM type."""
    if actual is None:
        return None

    if goal.uom in ['numeric_min', 'percentage_min']:
        # Higher is better
        if goal.target == 0:
            return 100.0 if actual > 0 else 0.0
        return min((actual / goal.target) * 100, 100.0)

    elif goal.uom in ['numeric_max', 'percentage_max']:
        # Lower is better
        if actual == 0:
            return 100.0
        if goal.target == 0:
            return 0.0
        return min((goal.target / actual) * 100, 100.0)

    elif goal.uom == 'zero':
        # Zero = success
        return 100.0 if actual == 0 else 0.0

    elif goal.uom == 'timeline':
        # Date-based: if completed on or before target = 100%
        return 100.0 if actual <= goal.target else max(0, 100 - ((actual - goal.target) / goal.target * 100))

    return 0.0

def get_employee_status(user_id):
    """Get the overall status of an employee's goals."""
    goals = Goal.query.filter_by(user_id=user_id).all()
    if not goals:
        return 'none'

    statuses = [g.status for g in goals]
    if all(s == 'approved' for s in statuses):
        return 'approved'
    elif any(s == 'submitted' for s in statuses):
        return 'submitted'
    else:
        return 'draft'

# ============================================
# ESCALATION & ANALYTICS HELPERS
# ============================================

def get_escalation_warnings():
    """Generate escalation warnings based on time-based rules."""
    warnings = []
    now = datetime.utcnow()

    # Rule 1: Employees with draft goals not submitted within 7 days of creation
    draft_goals = Goal.query.filter(Goal.status.in_(['draft', 'returned'])).all()
    for goal in draft_goals:
        days_since_creation = (now - goal.created_at).days
        if days_since_creation >= 7:
            employee = User.query.get(goal.user_id)
            warnings.append({
                'type': 'employee',
                'severity': 'warning' if days_since_creation < 14 else 'danger',
                'message': f'<strong>{employee.name}</strong> has not submitted goal "<em>{goal.title}</em>" for {days_since_creation} days',
                'action': 'Submit Goals',
                'link': url_for('employee_goals')
            })

    # Rule 2: Managers with pending approvals for 5+ days
    submitted_goals = Goal.query.filter_by(status='submitted').all()
    manager_pending = {}
    for goal in submitted_goals:
        employee = User.query.get(goal.user_id)
        if employee and employee.manager_id:
            manager = User.query.get(employee.manager_id)
            days_pending = (now - goal.created_at).days
            if days_pending >= 5:
                key = manager.id
                if key not in manager_pending:
                    manager_pending[key] = {'manager': manager, 'count': 0, 'max_days': 0}
                manager_pending[key]['count'] += 1
                manager_pending[key]['max_days'] = max(manager_pending[key]['max_days'], days_pending)

    for data in manager_pending.values():
        warnings.append({
            'type': 'manager',
            'severity': 'warning' if data['max_days'] < 10 else 'danger',
            'message': f"<strong>{data['manager'].name}</strong> has <strong>{data['count']}</strong> goal(s) pending approval for {data['max_days']}+ days",
            'action': 'Review Team',
            'link': url_for('manager_team')
        })

    # Rule 3: Check-in window closing soon (simulate current quarter)
    current_month = now.month
    quarter_map = {1: 'Q3', 2: 'Q3', 3: 'Q3', 4: 'Q4', 5: 'Q4', 6: 'Q4',
                   7: 'Q1', 8: 'Q1', 9: 'Q1', 10: 'Q2', 11: 'Q2', 12: 'Q2'}
    current_quarter = quarter_map.get(current_month, 'Q1')

    # Check if employees have missing check-ins for current quarter
    all_employees = User.query.filter_by(role='employee').all()
    approved_employees = [e for e in all_employees if get_employee_status(e.id) == 'approved']

    for emp in approved_employees:
        goals = Goal.query.filter_by(user_id=emp.id, status='approved').all()
        missing_checkins = 0
        for goal in goals:
            ci = CheckIn.query.filter_by(goal_id=goal.id, quarter=current_quarter).first()
            if not ci:
                missing_checkins += 1

        if missing_checkins > 0:
            warnings.append({
                'type': 'checkin',
                'severity': 'info',
                'message': f"<strong>{emp.name}</strong> has <strong>{missing_checkins}</strong> missing {current_quarter} check-in(s)",
                'action': 'Check-In',
                'link': url_for('employee_checkin', quarter=current_quarter)
            })

    return warnings

def get_goal_distribution():
    """Get goal distribution by Thrust Area and UoM type."""
    goals = Goal.query.all()

    thrust_distribution = {}
    uom_distribution = {}

    for goal in goals:
        thrust_distribution[goal.thrust_area] = thrust_distribution.get(goal.thrust_area, 0) + 1
        uom_distribution[goal.uom] = uom_distribution.get(goal.uom, 0) + 1

    return thrust_distribution, uom_distribution

def get_manager_leaderboard():
    """Get manager effectiveness leaderboard."""
    managers = User.query.filter_by(role='manager').all()
    leaderboard = []

    for manager in managers:
        team = User.query.filter_by(manager_id=manager.id).all()
        team_size = len(team)

        if team_size == 0:
            continue

        total_checkins = 0
        completed_checkins = 0

        for emp in team:
            goals = Goal.query.filter_by(user_id=emp.id, status='approved').all()
            for goal in goals:
                for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                    total_checkins += 1
                    ci = CheckIn.query.filter_by(goal_id=goal.id, quarter=q).first()
                    if ci and ci.status in ['on_track', 'completed']:
                        completed_checkins += 1

        completion_rate = (completed_checkins / total_checkins * 100) if total_checkins > 0 else 0

        leaderboard.append({
            'manager': manager,
            'team_size': team_size,
            'total_checkins': total_checkins,
            'completed_checkins': completed_checkins,
            'completion_rate': round(completion_rate, 1)
        })

    # Sort by completion rate descending
    leaderboard.sort(key=lambda x: x['completion_rate'], reverse=True)
    return leaderboard

# ============================================
# FORMS
# ============================================

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class GoalForm(FlaskForm):
    thrust_area = SelectField('Thrust Area', choices=[
        ('Revenue', 'Revenue'),
        ('Customer', 'Customer'),
        ('Operations', 'Operations'),
        ('People', 'People'),
        ('Innovation', 'Innovation'),
        ('Compliance', 'Compliance')
    ], validators=[DataRequired()])
    title = StringField('Goal Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    uom = SelectField('Unit of Measure', choices=[
        ('numeric_min', 'Numeric (Higher is Better)'),
        ('numeric_max', 'Numeric (Lower is Better)'),
        ('percentage_min', 'Percentage (Higher is Better)'),
        ('percentage_max', 'Percentage (Lower is Better)'),
        ('timeline', 'Timeline (Date-based)'),
        ('zero', 'Zero-based (Zero = Success)')
    ], validators=[DataRequired()])
    target = FloatField('Target Value', validators=[DataRequired()])
    weightage = FloatField('Weightage (%)', validators=[
        DataRequired(),
        NumberRange(min=10, max=100, message='Weightage must be between 10% and 100%')
    ])
    submit = SubmitField('Add Goal')

    def validate_weightage(self, field):
        # Get current total weightage for the user
        current_total = db.session.query(db.func.sum(Goal.weightage)).filter(
            Goal.user_id == current_user.id,
            Goal.status.in_(['draft', 'submitted', 'returned'])
        ).scalar() or 0

        if current_total + field.data > 100:
            raise ValidationError(f'Total weightage would exceed 100%. Current: {current_total}%, Adding: {field.data}%, Remaining: {100 - current_total}%')

        # Check max 8 goals
        goal_count = Goal.query.filter_by(user_id=current_user.id).count()
        if goal_count >= 8:
            raise ValidationError('Maximum 8 goals allowed per employee.')

# ============================================
# AUTH ROUTES
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'manager':
        return redirect(url_for('manager_team'))
    else:
        return redirect(url_for('employee_goals'))

# ============================================
# EMPLOYEE ROUTES
# ============================================

@app.route('/employee/goals', methods=['GET', 'POST'])
@employee_required
def employee_goals():
    form = GoalForm()
    cycle_open = get_cycle_status()

    if form.validate_on_submit() and cycle_open:
        goal = Goal(
            user_id=current_user.id,
            thrust_area=form.thrust_area.data,
            title=form.title.data,
            description=form.description.data,
            uom=form.uom.data,
            target=form.target.data,
            weightage=form.weightage.data,
            status='draft'
        )
        db.session.add(goal)
        db.session.commit()
        flash('Goal added successfully!', 'success')
        return redirect(url_for('employee_goals'))

    goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.created_at.desc()).all()
    total_weightage = sum(g.weightage for g in goals)

    approved_weightage = sum(g.weightage for g in goals if g.status == 'approved')

    return render_template('goals.html', 
                         form=form, 
                         goals=goals, 
                         total_weightage=total_weightage,
                         approved_weightage=approved_weightage,
                         cycle_open=cycle_open)

@app.route('/employee/goals/<int:goal_id>/delete', methods=['POST'])
@employee_required
def employee_delete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('employee_goals'))
    if goal.is_locked:
        flash('Cannot delete a locked goal.', 'danger')
        return redirect(url_for('employee_goals'))

    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted.', 'info')
    return redirect(url_for('employee_goals'))

@app.route('/employee/goals/submit', methods=['POST'])
@employee_required
def employee_submit_goals():
    # Get all goals that can be submitted (draft + returned)
    goals = Goal.query.filter(
        Goal.user_id == current_user.id,
        Goal.status.in_(['draft', 'returned'])
    ).all()

    if not goals:
        flash('No goals to submit.', 'warning')
        return redirect(url_for('employee_goals'))

    total_w = sum(g.weightage for g in goals)
    if total_w != 100:
        flash(f'Total weightage must be 100%. Current: {total_w}%', 'danger')
        return redirect(url_for('employee_goals'))

    for goal in goals:
        goal.status = 'submitted'
    db.session.commit()

    # Simulated email notification
    manager = User.query.get(current_user.manager_id)
    if manager:
        flash(f'&#128231; Email sent to {manager.email}: {current_user.name} has submitted goals for review', 'info')

    flash('Goals submitted for manager review!', 'success')
    return redirect(url_for('employee_goals'))

@app.route('/employee/checkin', methods=['GET', 'POST'])
@employee_required
def employee_checkin():
    quarter = request.args.get('quarter', 'Q1')
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']

    goals = Goal.query.filter_by(user_id=current_user.id, status='approved').all()

    if request.method == 'POST':
        quarter = request.form.get('quarter', quarter)
        for goal in goals:
            planned_key = f'planned_{goal.id}'
            actual_key = f'actual_{goal.id}'
            status_key = f'status_{goal.id}'

            planned = request.form.get(planned_key, type=float)
            actual = request.form.get(actual_key, type=float)
            status = request.form.get(status_key, 'not_started')

            checkin = CheckIn.query.filter_by(goal_id=goal.id, quarter=quarter).first()
            if not checkin:
                checkin = CheckIn(goal_id=goal.id, quarter=quarter)
                db.session.add(checkin)

            checkin.planned = planned
            checkin.actual = actual
            checkin.status = status
            checkin.score = calculate_score(goal, actual)
            checkin.updated_at = datetime.utcnow()

        db.session.commit()

        # Simulated email notification
        manager = User.query.get(current_user.manager_id)
        if manager:
            flash(f'&#128231; Email sent to {manager.email}: {current_user.name} has completed {quarter} check-in', 'info')

        flash(f'{quarter} check-in saved successfully!', 'success')
        return redirect(url_for('employee_checkin', quarter=quarter))

    checkins = {}
    for goal in goals:
        ci = CheckIn.query.filter_by(goal_id=goal.id, quarter=quarter).first()
        if ci:
            checkins[goal.id] = ci

    return render_template('checkin.html', 
                         goals=goals, 
                         checkins=checkins, 
                         quarter=quarter, 
                         quarters=quarters)

# ============================================
# MANAGER ROUTES
# ============================================

@app.route('/manager/team')
@manager_required
def manager_team():
    team_members = User.query.filter_by(manager_id=current_user.id).all()
    team_data = []

    for emp in team_members:
        goals = Goal.query.filter_by(user_id=emp.id).all()
        total = len(goals)
        submitted = len([g for g in goals if g.status == 'submitted'])
        approved = len([g for g in goals if g.status == 'approved'])

        team_data.append({
            'employee': emp,
            'total': total,
            'submitted_count': submitted,
            'approved_count': approved
        })

    return render_template('team.html', team_data=team_data)

@app.route('/manager/approve/<int:employee_id>')
@manager_required
def manager_approve_view(employee_id):
    employee = User.query.get_or_404(employee_id)
    if employee.manager_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('manager_team'))

    goals = Goal.query.filter_by(user_id=employee_id).order_by(Goal.created_at.desc()).all()
    return render_template('approve.html', employee=employee, goals=goals)

@app.route('/manager/approve/goal/<int:goal_id>', methods=['POST'])
@manager_required
def manager_approve_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    employee = User.query.get(goal.user_id)

    if employee.manager_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('manager_team'))

    goal.status = 'approved'
    goal.is_locked = True
    db.session.commit()

    # Simulated email notification
    flash(f'&#128231; Email sent to {employee.email}: Your goal "{goal.title}" has been approved', 'info')
    flash(f'Goal "{goal.title}" approved!', 'success')
    return redirect(url_for('manager_approve_view', employee_id=employee.id))

@app.route('/manager/return/goal/<int:goal_id>', methods=['POST'])
@manager_required
def manager_return_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    employee = User.query.get(goal.user_id)

    if employee.manager_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('manager_team'))

    comment = request.form.get('comment', '')
    goal.status = 'returned'
    goal.is_locked = False
    goal.manager_comment = comment
    db.session.commit()

    # Simulated email notification
    flash(f'&#128231; Email sent to {employee.email}: Your goal "{goal.title}" has been returned for revision', 'info')
    flash(f'Goal returned to {employee.name} for revision.', 'warning')
    return redirect(url_for('manager_approve_view', employee_id=employee.id))

@app.route('/manager/checkin/<int:employee_id>')
@manager_required
def manager_checkin_view(employee_id):
    employee = User.query.get_or_404(employee_id)
    if employee.manager_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('manager_team'))

    quarter = request.args.get('quarter', 'Q1')
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']

    goals = Goal.query.filter_by(user_id=employee_id, status='approved').all()
    checkins = {}

    for goal in goals:
        ci = CheckIn.query.filter_by(goal_id=goal.id, quarter=quarter).first()
        if ci:
            checkins[goal.id] = ci

    return render_template('checkin_view.html', 
                         employee=employee, 
                         goals=goals, 
                         checkins=checkins, 
                         quarter=quarter, 
                         quarters=quarters)

@app.route('/manager/comment/<int:checkin_id>', methods=['POST'])
@manager_required
def manager_add_comment(checkin_id):
    checkin = CheckIn.query.get_or_404(checkin_id)
    goal = Goal.query.get(checkin.goal_id)
    employee = User.query.get(goal.user_id)

    if employee.manager_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('manager_team'))

    comment = request.form.get('comment', '')
    checkin.manager_comment = comment
    db.session.commit()

    # Simulated email notification
    flash(f'&#128231; Email sent to {employee.email}: Manager feedback added on {checkin.quarter} check-in', 'info')
    flash('Comment saved.', 'success')
    return redirect(url_for('manager_checkin_view', employee_id=employee.id, quarter=checkin.quarter))

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    all_employees = User.query.filter_by(role='employee').all()
    total = len(all_employees)

    status_data = {}
    approved_count = 0
    submitted_count = 0
    draft_count = 0

    for emp in all_employees:
        status = get_employee_status(emp.id)
        status_data[emp.id] = status
        if status == 'approved':
            approved_count += 1
        elif status == 'submitted':
            submitted_count += 1
        else:
            draft_count += 1

    audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    cycle_open = get_cycle_status()

    # NEW: Analytics data
    thrust_distribution, uom_distribution = get_goal_distribution()
    manager_leaderboard = get_manager_leaderboard()
    escalation_warnings = get_escalation_warnings()

    return render_template('dashboard.html',
                         all_employees=all_employees,
                         status_data=status_data,
                         total=total,
                         approved_count=approved_count,
                         submitted_count=submitted_count,
                         draft_count=draft_count,
                         audit_logs=audit_logs,
                         cycle_open=cycle_open,
                         thrust_distribution=thrust_distribution,
                         uom_distribution=uom_distribution,
                         manager_leaderboard=manager_leaderboard,
                         escalation_warnings=escalation_warnings)

@app.route('/admin/toggle-cycle', methods=['POST'])
@admin_required
def admin_toggle_cycle():
    current = get_cycle_status()
    set_cycle_status(not current)
    action = 'opened' if not current else 'closed'
    log_audit(f'cycle_{action}')
    flash(f'Goal window {action} successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/employee/<int:employee_id>/unlock', methods=['POST'])
@admin_required
def admin_unlock_goal(employee_id):
    reason = request.form.get('reason', '')
    goals = Goal.query.filter_by(user_id=employee_id, is_locked=True).all()

    for goal in goals:
        goal.is_locked = False
        goal.status = 'draft'

    db.session.commit()
    log_audit('goal_unlocked', 'user', employee_id, reason)
    flash('Goals unlocked successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/shared-goals')
@admin_required
def admin_shared_goals():
    flash('Shared goals feature coming soon!', 'info')
    return redirect(url_for('admin_dashboard'))

# ============================================
# EXPORT ROUTES
# ============================================

@app.route('/export/goals')
@login_required
def export_goals():
    if current_user.role == 'employee':
        flash('Access denied.', 'danger')
        return redirect(url_for('employee_goals'))

    # Build export data
    data = []
    employees = User.query.filter_by(role='employee').all()

    for emp in employees:
        goals = Goal.query.filter_by(user_id=emp.id).all()
        for goal in goals:
            manager = User.query.get(emp.manager_id) if emp.manager_id else None
            data.append({
                'Employee': emp.name,
                'Email': emp.email,
                'Manager': manager.name if manager else 'N/A',
                'Thrust Area': goal.thrust_area,
                'Goal Title': goal.title,
                'Description': goal.description or '',
                'UoM': goal.uom,
                'Target': goal.target,
                'Weightage (%)': goal.weightage,
                'Status': goal.status,
                'Locked': 'Yes' if goal.is_locked else 'No',
                'Shared': 'Yes' if goal.is_shared else 'No'
            })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Goals', index=False)
    output.seek(0)

    return send_file(output, 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True, 
                    download_name='atomquest_goals_export.xlsx')

@app.route('/export/audit')
@admin_required
def export_audit():
    """Export audit log to CSV."""
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()

    data = []
    for log in logs:
        data.append({
            'Timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Admin': log.user.name,
            'Action': log.action,
            'Target Type': log.target_type or '',
            'Target ID': log.target_id or '',
            'Reason': log.reason or ''
        })

    df = pd.DataFrame(data)
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='atomquest_audit_log.csv'
    )

# ============================================
# SEED DATA & INIT
# ============================================

def seed_data():
    """Seed initial users if none exist."""
    if User.query.first():
        return

    # ============================================
    # CREATE USERS
    # ============================================

    # Admin
    admin = User(name='Admin User', email='admin@atomquest.com', password='admin123', role='admin')
    db.session.add(admin)

    # Manager 1 - Engineering Lead (high performer team)
    mgr1 = User(name='Alex Thompson', email='alex@atomquest.com', password='alex123', role='manager', department='Engineering')
    db.session.add(mgr1)

    # Manager 2 - Sales Director (mixed performance team)
    mgr2 = User(name='Lisa Park', email='lisa@atomquest.com', password='lisa123', role='manager', department='Sales')
    db.session.add(mgr2)

    # Manager 3 - Operations Head (some delays)
    mgr3 = User(name='David Kumar', email='david@atomquest.com', password='david123', role='manager', department='Operations')
    db.session.add(mgr3)

    db.session.commit()

    # Employees under Manager 1 (Alex - Engineering) - HIGH PERFORMERS
    emp1 = User(name='Employee User', email='employee@atomquest.com', password='employee123',
                role='employee', manager_id=mgr1.id, department='Engineering')
    emp2 = User(name='Sarah Chen', email='sarah@atomquest.com', password='sarah123',
                role='employee', manager_id=mgr1.id, department='Engineering')

    # Employees under Manager 2 (Lisa - Sales) - MIXED
    emp3 = User(name='Mike Ross', email='mike@atomquest.com', password='mike123',
                role='employee', manager_id=mgr2.id, department='Sales')
    emp4 = User(name='Emma Wilson', email='emma@atomquest.com', password='emma123',
                role='employee', manager_id=mgr2.id, department='Sales')

    # Employees under Manager 3 (David - Operations) - SOME DELAYS
    emp5 = User(name='James Lee', email='james@atomquest.com', password='james123',
                role='employee', manager_id=mgr3.id, department='Operations')
    emp6 = User(name='Priya Sharma', email='priya@atomquest.com', password='priya123',
                role='employee', manager_id=mgr3.id, department='Operations')

    db.session.add_all([emp1, emp2, emp3, emp4, emp5, emp6])

    # Set cycle open by default
    config = AppConfig(key='cycle_open', value='true')
    db.session.add(config)

    db.session.commit()

    # Refresh to get assigned IDs
    for user in [admin, mgr1, mgr2, mgr3, emp1, emp2, emp3, emp4, emp5, emp6]:
        db.session.refresh(user)

    # ============================================
    # GOALS - MANAGER 1 TEAM (Alex - Engineering)
    # ============================================

    # Employee 1 - Employee User (ALL APPROVED - consistent performer)
    e1_goals = [
        Goal(user_id=emp1.id, thrust_area='Revenue', title='Increase revenue by 10%',
              description='Drive Q1 sales growth through new client acquisition', uom='percentage_min',
              target=20.0, weightage=30.0, status='approved', is_locked=True),
        Goal(user_id=emp1.id, thrust_area='Operations', title='Lower operation cost',
              description='Reduce operational expenses by optimizing processes', uom='percentage_max',
              target=30.0, weightage=25.0, status='approved', is_locked=True),
        Goal(user_id=emp1.id, thrust_area='Compliance', title='Improve laws',
              description='Ensure 100% compliance with new regulations', uom='timeline',
              target=30.0, weightage=20.0, status='approved', is_locked=True),
        Goal(user_id=emp1.id, thrust_area='People', title='Hire 3 senior devs',
              description='Expand engineering team with senior talent', uom='numeric_min',
              target=3.0, weightage=25.0, status='approved', is_locked=True),
    ]
    for g in e1_goals:
        db.session.add(g)

    # Employee 2 - Sarah Chen (3 approved + 1 returned - needs rework)
    e2_goals = [
        Goal(user_id=emp2.id, thrust_area='Customer', title='Reduce churn to under 5%',
              description='Improve retention through better support', uom='percentage_max',
              target=5.0, weightage=35.0, status='approved', is_locked=True),
        Goal(user_id=emp2.id, thrust_area='Innovation', title='Launch new product feature',
              description='Release AI-powered recommendation engine', uom='zero',
              target=0.0, weightage=30.0, status='approved', is_locked=True),
        Goal(user_id=emp2.id, thrust_area='Revenue', title='Increase Q2 sales by 25%',
              description='Focus on enterprise accounts', uom='percentage_min',
              target=25.0, weightage=20.0, status='returned', is_locked=False,
              manager_comment='Target too aggressive for current market conditions. Please revise to 15% and add specific account names.'),
        Goal(user_id=emp2.id, thrust_area='People', title='Conduct 10 training sessions',
              description='Upskill team on new technologies', uom='numeric_min',
              target=10.0, weightage=15.0, status='approved', is_locked=True),
    ]
    for g in e2_goals:
        db.session.add(g)

    db.session.commit()
    for g in e1_goals + e2_goals:
        db.session.refresh(g)

    # ============================================
    # GOALS - MANAGER 2 TEAM (Lisa - Sales)
    # ============================================

    # Employee 3 - Mike Ross (ALL APPROVED - high performer)
    e3_goals = [
        Goal(user_id=emp3.id, thrust_area='Revenue', title='Close 50 enterprise deals',
              description='Target Fortune 500 companies', uom='numeric_min',
              target=50.0, weightage=40.0, status='approved', is_locked=True),
        Goal(user_id=emp3.id, thrust_area='Customer', title='Achieve NPS score of 70+',
              description='Improve customer satisfaction metrics', uom='numeric_min',
              target=70.0, weightage=25.0, status='approved', is_locked=True),
        Goal(user_id=emp3.id, thrust_area='Operations', title='Reduce sales cycle to 30 days',
              description='Streamline proposal and negotiation process', uom='numeric_max',
              target=30.0, weightage=20.0, status='approved', is_locked=True),
        Goal(user_id=emp3.id, thrust_area='Innovation', title='Implement CRM automation',
              description='Automate lead scoring and follow-ups', uom='zero',
              target=0.0, weightage=15.0, status='approved', is_locked=True),
    ]
    for g in e3_goals:
        db.session.add(g)

    # Employee 4 - Emma Wilson (2 approved + 2 draft - hasn't submitted yet)
    e4_goals = [
        Goal(user_id=emp4.id, thrust_area='Revenue', title='Generate $500K in new pipeline',
              description='Focus on mid-market segment', uom='numeric_min',
              target=500.0, weightage=35.0, status='draft', is_locked=False),
        Goal(user_id=emp4.id, thrust_area='Customer', title='Improve response time to 2 hours',
              description='Reduce average ticket response time', uom='numeric_max',
              target=2.0, weightage=25.0, status='draft', is_locked=False),
        Goal(user_id=emp4.id, thrust_area='People', title='Mentor 2 junior reps',
              description='Knowledge transfer to new team members', uom='numeric_min',
              target=2.0, weightage=20.0, status='approved', is_locked=True),
        Goal(user_id=emp4.id, thrust_area='Innovation', title='Adopt new sales methodology',
              description='Implement MEDDIC framework across team', uom='zero',
              target=0.0, weightage=20.0, status='approved', is_locked=True),
    ]
    for g in e4_goals:
        db.session.add(g)

    db.session.commit()
    for g in e3_goals + e4_goals:
        db.session.refresh(g)

    # ============================================
    # GOALS - MANAGER 3 TEAM (David - Operations)
    # ============================================

    # Employee 5 - James Lee (ALL APPROVED - solid performer)
    e5_goals = [
        Goal(user_id=emp5.id, thrust_area='Operations', title='Reduce downtime by 15%',
              description='Improve system reliability and uptime', uom='percentage_max',
              target=15.0, weightage=30.0, status='approved', is_locked=True),
        Goal(user_id=emp5.id, thrust_area='Compliance', title='Pass ISO 27001 audit',
              description='Achieve security certification', uom='zero',
              target=0.0, weightage=25.0, status='approved', is_locked=True),
        Goal(user_id=emp5.id, thrust_area='People', title='Train 20 staff on safety',
              description='Mandatory safety protocol training', uom='numeric_min',
              target=20.0, weightage=25.0, status='approved', is_locked=True),
        Goal(user_id=emp5.id, thrust_area='Revenue', title='Cut procurement costs 10%',
              description='Renegotiate vendor contracts', uom='percentage_max',
              target=10.0, weightage=20.0, status='approved', is_locked=True),
    ]
    for g in e5_goals:
        db.session.add(g)

    # Employee 6 - Priya Sharma (1 approved + 3 submitted - pending manager review)
    e6_goals = [
        Goal(user_id=emp6.id, thrust_area='Operations', title='Implement lean workflow',
              description='Reduce waste in production process', uom='percentage_max',
              target=20.0, weightage=30.0, status='submitted', is_locked=False),
        Goal(user_id=emp6.id, thrust_area='Customer', title='Reduce delivery defects to <1%',
              description='Quality control improvements', uom='percentage_max',
              target=1.0, weightage=25.0, status='submitted', is_locked=False),
        Goal(user_id=emp6.id, thrust_area='Innovation', title='Deploy AI quality scanner',
              description='Automated defect detection system', uom='zero',
              target=0.0, weightage=25.0, status='submitted', is_locked=False),
        Goal(user_id=emp6.id, thrust_area='People', title='Hire 5 warehouse operators',
              description='Staff expansion for peak season', uom='numeric_min',
              target=5.0, weightage=20.0, status='approved', is_locked=True),
    ]
    for g in e6_goals:
        db.session.add(g)

    db.session.commit()
    for g in e5_goals + e6_goals:
        db.session.refresh(g)

    # ============================================
    # CHECK-INS HELPER
    # ============================================

    def create_checkin(goal_id, quarter, planned, actual, status):
        score = None
        goal = Goal.query.get(goal_id)
        if goal and actual is not None:
            score = calculate_score(goal, actual)
        ci = CheckIn(
            goal_id=goal_id,
            quarter=quarter,
            planned=planned,
            actual=actual,
            score=score,
            status=status
        )
        db.session.add(ci)

    # ============================================
    # CHECK-INS - MANAGER 1 TEAM (Alex - HIGH COMPLETION)
    # ============================================

    # Employee 1 - Employee User (all quarters, all goals - 100% completion)
    for q, data in [('Q1', [(15,18,'on_track'),(25,22,'completed'),(30,28,'on_track'),(1,1,'on_track')]),
                     ('Q2', [(18,20,'completed'),(22,20,'completed'),(28,25,'on_track'),(2,3,'completed')]),
                     ('Q3', [(20,19,'on_track'),(20,18,'completed'),(25,30,'completed'),(3,3,'completed')]),
                     ('Q4', [(22,24,'completed'),(18,15,'completed'),(30,30,'completed'),(3,3,'completed')])]:
        for i, (planned, actual, status) in enumerate(data):
            create_checkin(e1_goals[i].id, q, planned, actual, status)

    # Employee 2 - Sarah Chen (missing some Q3 check-ins)
    for q, data in [('Q1', [(6,5.2,'on_track'),(0,0,'completed'),None,(3,4,'completed')]),
                     ('Q2', [(5.2,4.8,'completed'),(0,0,'completed'),None,(4,6,'completed')]),
                     ('Q3', [(4.8,5.5,'on_track'),(0,0,'completed'),None,(6,8,'completed')]),
                     ('Q4', [(5.5,4.5,'completed'),(1,0,'completed'),None,(8,10,'completed')])]:
        for i, item in enumerate(data):
            if item:
                create_checkin(e2_goals[i].id, q, item[0], item[1], item[2])

    # ============================================
    # CHECK-INS - MANAGER 2 TEAM (Lisa - MIXED)
    # ============================================

    # Employee 3 - Mike Ross (all quarters, all goals - 100% completion)
    for q, data in [('Q1', [(12,15,'on_track'),(65,68,'on_track'),(35,32,'on_track'),(0,0,'completed')]),
                     ('Q2', [(15,18,'on_track'),(68,72,'completed'),(32,28,'completed'),(0,0,'completed')]),
                     ('Q3', [(18,20,'completed'),(72,70,'on_track'),(28,25,'completed'),(0,0,'completed')]),
                     ('Q4', [(20,22,'completed'),(70,75,'completed'),(25,22,'completed'),(0,0,'completed')])]:
        for i, (planned, actual, status) in enumerate(data):
            create_checkin(e3_goals[i].id, q, planned, actual, status)

    # Employee 4 - Emma Wilson (only approved goals have check-ins, draft goals none)
    for q, data in [('Q1', [None,None,(1,2,'on_track'),(0,0,'completed')]),
                     ('Q2', [None,None,(2,2,'completed'),(0,0,'completed')]),
                     ('Q3', [None,None,(2,3,'on_track'),(0,0,'completed')]),
                     ('Q4', [None,None,(3,3,'completed'),(0,0,'completed')])]:
        for i, item in enumerate(data):
            if item:
                create_checkin(e4_goals[i].id, q, item[0], item[1], item[2])

    # ============================================
    # CHECK-INS - MANAGER 3 TEAM (David - SOME MISSING)
    # ============================================

    # Employee 5 - James Lee (all quarters, all goals - 100% completion)
    for q, data in [('Q1', [(18,16,'on_track'),(0,0,'completed'),(5,8,'on_track'),(12,10,'completed')]),
                     ('Q2', [(16,14,'completed'),(0,0,'completed'),(8,12,'completed'),(10,9,'completed')]),
                     ('Q3', [(14,13,'on_track'),(0,0,'completed'),(12,15,'completed'),(9,8,'completed')]),
                     ('Q4', [(13,12,'completed'),(0,0,'completed'),(15,20,'completed'),(8,7,'completed')])]:
        for i, (planned, actual, status) in enumerate(data):
            create_checkin(e5_goals[i].id, q, planned, actual, status)

    # Employee 6 - Priya Sharma (missing Q4 entirely, some Q3 missing)
    for q, data in [('Q1', [(8,10,'on_track'),(2,1.5,'completed'),(0,0,'completed'),(1,2,'on_track')]),
                     ('Q2', [(10,12,'completed'),(1.5,1.2,'completed'),(0,0,'completed'),(2,3,'completed')]),
                     ('Q3', [(12,14,'on_track'),(1.2,1.0,'completed'),None,(3,4,'completed')])]:
        for i, item in enumerate(data):
            if item:
                create_checkin(e6_goals[i].id, q, item[0], item[1], item[2])
    # Q4 - NO CHECKINS (simulates missing quarter)

    db.session.commit()

    # ============================================
    # MANAGER COMMENTS ON CHECK-INS
    # ============================================

    # Add comments for realism
    checkins_q2 = CheckIn.query.filter(CheckIn.quarter == 'Q2').all()
    for ci in checkins_q2[:8]:
        ci.manager_comment = 'Great progress this quarter. Keep focusing on the key metrics.'

    checkins_q4 = CheckIn.query.filter(CheckIn.quarter == 'Q4').all()
    for ci in checkins_q4[:5]:
        ci.manager_comment = 'Excellent year-end performance. Exceeded expectations.'

    # Add some critical feedback
    checkins_q3 = CheckIn.query.filter(CheckIn.quarter == 'Q3').all()
    for ci in checkins_q3[:3]:
        ci.manager_comment = 'Need to catch up on Q3 targets. Focus on closing gaps.'

    db.session.commit()

    # ============================================
    # AUDIT LOG ENTRIES
    # ============================================

    audit_entries = [
        AuditLog(user_id=admin.id, action='cycle_opened', target_type='config', target_id=1,
                 reason='FY2025 goal setting cycle started'),
        AuditLog(user_id=admin.id, action='goal_unlocked', target_type='user', target_id=emp2.id,
                 reason='Employee requested revision due to role change'),
        AuditLog(user_id=admin.id, action='manager_assigned', target_type='user', target_id=emp3.id,
                 reason='Reassigned to Sales Director Lisa Park'),
        AuditLog(user_id=admin.id, action='manager_assigned', target_type='user', target_id=emp5.id,
                 reason='Reassigned to Operations Head David Kumar'),
        AuditLog(user_id=admin.id, action='escalation_triggered', target_type='user', target_id=emp6.id,
                 reason='Goals pending manager approval for 5+ days'),
        AuditLog(user_id=admin.id, action='escalation_triggered', target_type='user', target_id=emp4.id,
                 reason='Draft goals not submitted within 7 days'),
    ]
    for entry in audit_entries:
        db.session.add(entry)

    db.session.commit()
    print("Seed data created successfully with 3 managers, 6 employees, and realistic check-in patterns!")
# ============================================
# APP INIT
# ============================================

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True)
