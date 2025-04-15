from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import logging
import base64

# Flask app setup
app = Flask(__name__)
app.secret_key = 'secret'  # Use os.urandom(24) in production
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "drexel.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)
app.jinja_env.filters['b64encode'] = lambda x: base64.b64encode(x).decode('utf-8') if x else ''
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    firstName = db.Column(db.String(150), nullable=False)
    lastName = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(150), nullable=False)
    major = db.Column(db.String(150), nullable=False)
    minor = db.Column(db.String(150))
    year = db.Column(db.String(50), nullable=False)
    coOp = db.Column(db.String(50))
    profilePic = db.Column(db.LargeBinary)

    def get_id(self):
        return str(self.id)

class Course(db.Model):
    crn = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(50), nullable=False)
    course_name = db.Column(db.String(150), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    day = db.Column(db.String(10), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Time conversion utilities
def time_to_minutes(time_str):
    if not time_str:
        return None
    time_str = time_str.strip().lower().replace(" ", "").replace("am", "AM").replace("pm", "PM")
    if ':' not in time_str:
        if len(time_str) == 3:
            time_str = f"{time_str[0:1]}:00{time_str[1:]}"
        elif len(time_str) == 4:
            time_str = f"{time_str[0:2]}:00{time_str[2:]}"
    if time_str.endswith('AM') and time_str != '12:00AM':
        hour, minute = map(int, time_str.replace('AM', '').split(':'))
    elif time_str.endswith('PM') and time_str != '12:00PM':
        hour, minute = map(int, time_str.replace('PM', '').split(':'))
        hour += 12
    elif time_str == '12:00AM':
        hour, minute = 0, 0
    elif time_str == '12:00PM':
        hour, minute = 12, 0
    else:
        raise ValueError(f"Invalid time format: {time_str}")
    return hour * 60 + minute

def minutes_to_time(minutes):
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    period = "AM" if hours < 12 else "PM"
    if hours == 0:
        hours = 12
    elif hours > 12:
        hours -= 12
    return f"{hours:02d}:{mins:02d}{period}"

# Scheduler helper function
def generate_schedule(courses_selected, start_time, end_time, spacing):
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    if start_minutes >= end_minutes:
        return None  # Invalid time range

    # Get all course instances
    all_courses = Course.query.filter(Course.course_code.in_(courses_selected)).all()
    if not all_courses:
        return None

    # Filter courses within time range
    filtered_courses = []
    for course in all_courses:
        course_start = time_to_minutes(course.start_time)
        course_end = time_to_minutes(course.end_time)
        if course_start >= start_minutes and course_end <= end_minutes:
            filtered_courses.append(course)

    if len(filtered_courses) < len(courses_selected):
        return None  # Not enough courses available

    # Group by course code to ensure one instance per course
    course_options = {}
    for course in filtered_courses:
        if course.course_code not in course_options:
            course_options[course.course_code] = []
        course_options[course.course_code].append(course)

    # Build schedule with conflict checking
    schedule = []
    used_times = {}  # {day: [(start, end), ...]}

    for course_code in courses_selected:
        if course_code not in course_options:
            continue
        for course in course_options[course_code]:
            start = time_to_minutes(course.start_time)
            end = time_to_minutes(course.end_time)
            day = course.day

            # Check for conflicts
            conflict = False
            if day in used_times:
                for used_start, used_end in used_times[day]:
                    if not (end <= used_start or start >= used_end):
                        conflict = True
                        break
            if conflict:
                continue

            # Check spacing
            if spacing == "spaced-out" and day in used_times:
                for used_start, used_end in used_times[day]:
                    if abs(start - used_end) < 60 and abs(used_start - end) < 60:  # Less than 1-hour gap
                        conflict = True
                        break
            if conflict:
                continue

            # Add to schedule
            schedule.append((course.day, course.course_code, course.course_name, course.start_time, course.end_time))
            if day not in used_times:
                used_times[day] = []
            used_times[day].append((start, end))
            break  # Move to next course after adding one instance

    return schedule if len(schedule) == len(courses_selected) else None

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        logger.debug(f"Login attempt: email={email}")
        user = User.query.filter_by(email=email, password=password).first()  # TODO: Hash password comparison
        if user:
            login_user(user)
            logger.debug(f"Login successful for {email}")
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            logger.debug("Login failed: Invalid credentials")
            flash('Invalid email or password.', 'error')
    return render_template('login.html', user=current_user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        firstName = request.form.get('firstName')
        lastName = request.form.get('lastName')
        year = request.form.get('year')
        coOp = request.form.get('coOp')
        password = request.form.get('password1')
        major = request.form.get('major')
        minor = request.form.get('minor')
        try:
            new_user = User(email=email, firstName=firstName, lastName=lastName, year=year,
                            coOp=coOp if coOp else None, password=password, major=major, minor=minor)
            db.session.add(new_user)
            db.session.commit()
            logger.debug(f"Signup successful for {email}, coOp: {coOp}")
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except db.IntegrityError:
            db.session.rollback()
            logger.debug(f"Signup failed: Email {email} already exists")
            flash('Email already exists.', 'error')
    return render_template('signup.html', user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', userName=current_user.firstName, user=current_user)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'profilePic' in request.files:
            file = request.files['profilePic']
            if file and file.filename != '':
                current_user.profilePic = file.read()
                db.session.commit()
                flash('Profile picture updated!', 'success')
        elif request.form.get('form_type') == 'profile':
            current_user.email = request.form.get('email')
            current_user.firstName = request.form.get('firstName')
            current_user.lastName = request.form.get('lastName')
            current_user.major = request.form.get('major')
            current_user.minor = request.form.get('minor')
            current_user.year = request.form.get('year')
            current_user.coOp = request.form.get('coOp')
            db.session.commit()
            flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/schedule')
@login_required
def schedule():
    return render_template('schedule.html', user=current_user)

@app.route('/save_schedule', methods=['POST'])
@login_required
def save_schedule():
    courses = [
        request.form.get('course1'),
        request.form.get('course2'),
        request.form.get('course3'),
        request.form.get('course4'),
        request.form.get('course5')
    ]
    start_time = request.form.get('startTime')
    end_time = request.form.get('endTime')
    spacing = request.form.get('spacing')

    # Filter out empty selections
    courses_selected = [course for course in courses if course]
    if not courses_selected:
        flash('Please select at least one course.', 'error')
        return redirect(url_for('schedule'))

    # Generate schedule
    schedule = generate_schedule(courses_selected, start_time, end_time, spacing)
    if schedule:
        session['schedule'] = schedule
        flash('Schedule generated successfully!', 'success')
    else:
        flash('Could not generate a conflict-free schedule with your preferences.', 'error')
        return redirect(url_for('schedule'))

    return redirect(url_for('display_schedule'))

@app.route('/display_schedule')
@login_required
def display_schedule():
    schedule = session.get('schedule', [])
    if not schedule:
        flash('No schedule generated. Please select courses.', 'error')
        return redirect(url_for('schedule'))
    return render_template('schedule_result.html', schedule=schedule, time_to_minutes=time_to_minutes)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        if Course.query.count() == 0:
            mock_courses = [
                (10001, 'CS 164', 'Intro to Computer Science', '08:00AM', '09:00AM', 'Monday'),
                (10002, 'CS 164', 'Intro to Computer Science', '10:00AM', '11:00AM', 'Wednesday'),
                (10003, 'CS 164', 'Intro to Computer Science', '02:00PM', '03:00PM', 'Friday'),
                (10004, 'MATH 121', 'Calculus I', '09:00AM', '10:00AM', 'Tuesday'),
                (10005, 'MATH 121', 'Calculus I', '11:00AM', '12:00PM', 'Thursday'),
                (10006, 'MATH 121', 'Calculus I', '01:00PM', '02:00PM', 'Monday'),
                (10007, 'ENGL 101', 'Composition and Rhetoric I', '10:00AM', '11:00AM', 'Monday'),
                (10008, 'ENGL 101', 'Composition and Rhetoric I', '01:00PM', '02:00PM', 'Wednesday'),
                (10009, 'ENGL 101', 'Composition and Rhetoric I', '03:00PM', '04:00PM', 'Friday'),
                (10010, 'CHEM 101', 'General Chemistry I', '08:00AM', '09:00AM', 'Thursday'),
                (10011, 'CHEM 101', 'General Chemistry I', '12:00PM', '01:00PM', 'Tuesday'),
                (10012, 'CHEM 101', 'General Chemistry I', '02:00PM', '03:00PM', 'Wednesday'),
                (10013, 'COOP 101', 'Career Management', '09:00AM', '10:00AM', 'Friday'),
                (10014, 'COOP 101', 'Career Management', '11:00AM', '12:00PM', 'Monday'),
                (10015, 'COOP 101', 'Career Management', '03:00PM', '04:00PM', 'Tuesday'),
                (10016, 'UNIV 101', 'The Drexel Experience', '08:00AM', '09:00AM', 'Wednesday'),
                (10017, 'UNIV 101', 'The Drexel Experience', '12:00PM', '01:00PM', 'Friday'),
                (10018, 'UNIV 101', 'The Drexel Experience', '01:00PM', '02:00PM', 'Thursday'),
                # New courses added below
                (10019, 'COM 230', 'Techniques of Speaking', '09:00AM', '10:00AM', 'Monday'),
                (10020, 'COM 230', 'Techniques of Speaking', '11:00AM', '12:00PM', 'Wednesday'),
                (10021, 'COM 230', 'Techniques of Speaking', '02:00PM', '03:00PM', 'Friday'),
                (10022, 'ENGL 111', 'English Composition I', '08:00AM', '09:00AM', 'Tuesday'),
                (10023, 'ENGL 111', 'English Composition I', '10:00AM', '11:00AM', 'Thursday'),
                (10024, 'ENGL 111', 'English Composition I', '01:00PM', '02:00PM', 'Friday'),
                (10025, 'ENGL 112', 'Composition and Rhetoric II', '09:00AM', '10:00AM', 'Wednesday'),
                (10026, 'ENGL 112', 'Composition and Rhetoric II', '12:00PM', '01:00PM', 'Monday'),
                (10027, 'ENGL 112', 'Composition and Rhetoric II', '03:00PM', '04:00PM', 'Thursday'),
                (10028, 'ENGL 113', 'Composition and Rhetoric III', '08:00AM', '09:00AM', 'Friday'),
                (10029, 'ENGL 113', 'Composition and Rhetoric III', '11:00AM', '12:00PM', 'Tuesday'),
                (10030, 'ENGL 113', 'Composition and Rhetoric III', '02:00PM', '03:00PM', 'Monday'),
                (10031, 'PHIL 311', 'Ethics and Information Technology', '10:00AM', '11:00AM', 'Tuesday'),
                (10032, 'PHIL 311', 'Ethics and Information Technology', '01:00PM', '02:00PM', 'Wednesday'),
                (10033, 'PHIL 311', 'Ethics and Information Technology', '03:00PM', '04:00PM', 'Thursday'),
                (10034, 'ENGL 102', 'Composition and Rhetoric II', '08:00AM', '09:00AM', 'Monday'),
                (10035, 'ENGL 102', 'Composition and Rhetoric II', '10:00AM', '11:00AM', 'Wednesday'),
                (10036, 'ENGL 102', 'Composition and Rhetoric II', '02:00PM', '03:00PM', 'Tuesday'),
                (10037, 'ENGL 103', 'Composition and Rhetoric III', '09:00AM', '10:00AM', 'Thursday'),
                (10038, 'ENGL 103', 'Composition and Rhetoric III', '12:00PM', '01:00PM', 'Wednesday'),
                (10039, 'ENGL 103', 'Composition and Rhetoric III', '03:00PM', '04:00PM', 'Monday'),
            ]
            for course in mock_courses:
                db.session.add(Course(crn=course[0], course_code=course[1], course_name=course[2],
                                     start_time=course[3], end_time=course[4], day=course[5]))
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)