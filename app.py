from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/test.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

#######################################
# MODELS
#######################################
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_teacher = db.Column(db.Boolean, default=False)
    quota = db.Column(db.Integer, default=3)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class JoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

#######################################
# AUTHENTICATION ROUTES
#######################################
@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register', role=role))
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            is_teacher=(role == 'teacher')
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful')
        return redirect(url_for('login', role=role))
    return render_template('register.html', role=role)

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('teacher_dashboard' if user.is_teacher else 'student_dashboard'))
        flash('Invalid credentials')
    return render_template('login.html', role=role)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

#######################################
# DASHBOARDS
#######################################
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if not current_user.is_teacher:
        return redirect(url_for('student_dashboard'))
    projects = Project.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher_dashboard.html', projects=projects)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.is_teacher:
        return redirect(url_for('teacher_dashboard'))
    interests = JoinRequest.query.filter_by(student_id=current_user.id).all()
    return render_template('student_dashboard.html', interests=interests)

#######################################
# PROJECT MANAGEMENT
#######################################
@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def create_project():
    if not current_user.is_teacher:
        flash('Only teachers can create projects')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        project = Project(name=name, description=description, teacher_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully')
        return redirect(url_for('teacher_dashboard'))
    return render_template('create_project.html')

#######################################
# JOIN REQUEST MANAGEMENT
#######################################
@app.route('/teacher/join_requests')
@login_required
def view_join_requests():
    if not current_user.is_teacher:
        return redirect(url_for('index'))
    requests = JoinRequest.query.join(Project).filter(Project.teacher_id==current_user.id).all()
    return render_template('join_requests.html', requests=requests)

@app.route('/teacher/handle_request/<int:request_id>/<decision>', methods=['POST'])
@login_required
def handle_join_request(request_id, decision):
    req = JoinRequest.query.get_or_404(request_id)
    if req.project.teacher_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    req.status = decision if decision in ['approved','rejected'] else req.status
    db.session.commit()
    return redirect(url_for('view_join_requests'))

if __name__ == '__main__':
    app.run(debug=True)
