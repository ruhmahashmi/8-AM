from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
import os
import logging
import base64
from datetime import datetime

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
    credits = db.Column(db.Integer, nullable=False, default=3) 

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course1 = db.Column(db.String(50))
    course2 = db.Column(db.String(50))
    course3 = db.Column(db.String(50))
    course4 = db.Column(db.String(50))
    course5 = db.Column(db.String(50))
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    spacing = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    try:
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
    except Exception as e:
        logger.error(f"Time conversion error for {time_str}: {str(e)}")
        return None

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
    logger.debug(f"Generating schedule with courses: {courses_selected}, start: {start_time}, end: {end_time}, spacing: {spacing}")
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or start_minutes >= end_minutes:
        logger.error(f"Invalid time range: start={start_time}, end={end_time}")
        return None

    # Get all course instances
    all_courses = Course.query.filter(Course.course_code.in_(courses_selected)).all()
    logger.debug(f"Found {len(all_courses)} courses: {[c.course_code + ' ' + c.start_time + '-' + c.end_time + ' ' + c.day for c in all_courses]}")
    if not all_courses:
        logger.error(f"No courses found for {courses_selected}")
        return None

    # Filter courses (include if start time is in range or course overlaps with range)
    filtered_courses = []
    for course in all_courses:
        course_start = time_to_minutes(course.start_time)
        course_end = time_to_minutes(course.end_time)
        if course_start is None or course_end is None:
            logger.warning(f"Invalid time for course {course.course_code}: {course.start_time}-{course.end_time}")
            continue
        if (course_start >= start_minutes and course_start <= end_minutes) or \
           (course_end > start_minutes and course_start < end_minutes):
            filtered_courses.append(course)
            logger.debug(f"Added course {course.course_code} ({course.start_time}-{course.end_time}, {course.day}) to filtered list")

    logger.debug(f"Filtered {len(filtered_courses)} courses within {start_time}-{end_time}")
    if not filtered_courses:
        logger.error(f"No courses available within time range {start_time}-{end_time}")
        return None

    # Group by course code
    course_options = {}
    for course in filtered_courses:
        if course.course_code not in course_options:
            course_options[course.course_code] = []
        course_options[course.course_code].append(course)
    logger.debug(f"Course options: {course_options.keys()}")

    # Backtracking to find a valid schedule
    def backtrack(selected_courses, used_times, course_codes):
        if len(selected_courses) == len(course_codes):
            logger.debug(f"Valid schedule found: {selected_courses}")
            return selected_courses
        current_code = course_codes[len(selected_courses)]
        if current_code not in course_options:
            logger.debug(f"No options for {current_code}")
            return None
        for course in course_options[current_code]:
            start = time_to_minutes(course.start_time)
            end = time_to_minutes(course.end_time)
            day = course.day
            if start is None or end is None:
                continue

            # Check for conflicts
            conflict = False
            if day in used_times:
                for used_start, used_end in used_times[day]:
                    if not (end <= used_start or start >= used_end):
                        conflict = True
                        break
            if conflict:
                logger.debug(f"Conflict for {course.course_code} on {day} {course.start_time}-{course.end_time}")
                continue

            # Check spacing
            if spacing == "spaced-out" and day in used_times:
                for used_start, used_end in used_times[day]:
                    if used_end < start and start - used_end < 60:  # Less than 1-hour gap before
                        conflict = True
                        break
                    if end < used_start and used_start - end < 60:  # Less than 1-hour gap after
                        conflict = True
                        break
            if conflict:
                logger.debug(f"Spacing conflict for {course.course_code} on {day} {course.start_time}-{course.end_time}")
                continue

            # Add course and recurse
            new_used_times = used_times.copy()
            if day not in new_used_times:
                new_used_times[day] = []
            new_used_times[day].append((start, end))
            result = backtrack(
                selected_courses + [(course.day, course.course_code, course.course_name, course.start_time, course.end_time)],
                new_used_times,
                course_codes
            )
            if result:
                return result
        logger.debug(f"No valid option for {current_code}")
        return None

    schedule = backtrack([], {}, courses_selected)
    if not schedule:
        logger.error(f"Failed to generate schedule for {courses_selected} with spacing={spacing}")
    else:
        logger.info(f"Generated schedule: {schedule}")
    return schedule

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
        coOp = request.form.get('co-op')
        password = request.form.get('password1')
        password_confirm = request.form.get('password2')
        major = request.form.get('major')
        minor = request.form.get('minor')
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))
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

    # Fetch distinct courses by course_code and course_name
    courses = db.session.query(Course.course_code, Course.course_name).distinct(Course.course_code).order_by(Course.course_code).all()
    # Convert the result into a list of objects with course_code and course_name attributes
    class CourseObj:
        def __init__(self, course_code, course_name):
            self.course_code = course_code
            self.course_name = course_name
    courses = [CourseObj(course[0], course[1]) for course in courses]

    courses = Course.query.all()
    print(courses)
    return render_template('schedule.html', user=current_user, courses=courses)

@app.route('/save_schedule', methods=['POST'])
@login_required
def save_schedule():
    try:
        logger.debug(f"Received form data for user {current_user.id}: {request.form}")

        # Clear previous schedule_id to prevent invalid redirects
        if 'schedule_id' in session:
            session.pop('schedule_id')

        # Get all course fields dynamically
        courses_selected = []
        i = 1
        while True:
            course = request.form.get(f'course{i}')
            if not course:
                break
            courses_selected.append(course)
            i += 1

        start_time = request.form.get('startTime')
        end_time = request.form.get('endTime')
        spacing = request.form.get('spacing', 'compact')

        logger.debug(f"Courses selected: {courses_selected}, Start: {start_time}, End: {end_time}, Spacing: {spacing}")

        if not courses_selected:
            flash('Please select at least one course.', 'error')
            return redirect(url_for('schedule'))

        # Validate time range
        start_minutes = time_to_minutes(start_time)
        end_minutes = time_to_minutes(end_time)
        if start_minutes is None or end_minutes is None:
            flash('Invalid time format. Please use HH:MM AM/PM.', 'error')
            return redirect(url_for('schedule'))
        if start_minutes >= end_minutes:
            flash('End time must be after start time.', 'error')
            return redirect(url_for('schedule'))

        # Generate schedule
        schedule = generate_schedule(courses_selected, start_time, end_time, spacing)
        if schedule:
            session['schedule'] = schedule
            session['courses_selected'] = courses_selected
            session['start_time'] = start_time
            session['end_time'] = end_time
            session['spacing'] = spacing
            flash('Schedule generated successfully! Save it to keep it.', 'success')
            return redirect(url_for('display_schedule'))
        else:
            flash('Could not generate a conflict-free schedule. Try fewer courses, a wider time range, or compact spacing.', 'error')
            return redirect(url_for('schedule'))
    except Exception as e:
        logger.error(f"Unexpected error in save_schedule for user {current_user.id}: {e}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('schedule'))

    
@app.route('/save_current_schedule', methods=['POST'])
@login_required
def save_current_schedule():
    schedule = session.get('schedule')
    courses_selected = session.get('courses_selected')
    start_time = session.get('start_time')
    end_time = session.get('end_time')
    spacing = session.get('spacing')
    
    if not schedule or not courses_selected:
        logger.error(f"No schedule or courses to save for user {current_user.id}")
        return jsonify({'success': False, 'message': 'No schedule to save.'}), 400

    # Extract courses for database
    course_dict = {f'course{i+1}': courses_selected[i] if i < len(courses_selected) else None for i in range(5)}

    # Save to database
    new_schedule = Schedule(
        user_id=current_user.id,
        course1=course_dict.get('course1'),
        course2=course_dict.get('course2'),
        course3=course_dict.get('course3'),
        course4=course_dict.get('course4'),
        course5=course_dict.get('course5'),
        start_time=start_time,
        end_time=end_time,
        spacing=spacing
    )
    db.session.add(new_schedule)
    db.session.commit()
    logger.info(f"Schedule ID {new_schedule.id} saved for user {current_user.id}")

    session['schedule_id'] = new_schedule.id
    return jsonify({'success': True, 'message': f'Schedule #{new_schedule.id} saved successfully!'}), 200

@app.route('/saved_schedules')
@login_required
def saved_schedules():
    schedules = Schedule.query.filter_by(user_id=current_user.id).order_by(Schedule.created_at.desc()).all()
    return render_template('saved_schedules.html', schedules=schedules)

@app.route('/display_schedule')
@login_required
def display_schedule():
    logger.debug(f"Accessing display_schedule for user {current_user.id}, session: {session}, args: {request.args}")
    schedule_id = request.args.get('schedule_id', session.get('schedule_id'), type=int)
    logger.debug(f"Schedule ID: {schedule_id}, source: {'request.args' if request.args.get('schedule_id') else 'session' if session.get('schedule_id') else 'none'}")
    schedule = session.get('schedule', [])

    if schedule_id:
        saved_schedule = Schedule.query.get(schedule_id)
        if saved_schedule and saved_schedule.user_id == current_user.id:
            courses_selected = list(set([course for course in [
                saved_schedule.course1, saved_schedule.course2, saved_schedule.course3,
                saved_schedule.course4, saved_schedule.course5
            ] if course]))
            logger.debug(f"Regenerating schedule ID {schedule_id} with courses {courses_selected}")
            schedule = generate_schedule(
                courses_selected,
                saved_schedule.start_time, 
                saved_schedule.end_time,
                saved_schedule.spacing
            )
            if schedule:
                session['schedule'] = schedule
                session['schedule_id'] = schedule_id
                session['courses_selected'] = courses_selected
                session['start_time'] = saved_schedule.start_time
                session['end_time'] = saved_schedule.end_time
                session['spacing'] = saved_schedule.spacing
                logger.info(f"Regenerated schedule ID {schedule_id} for user {current_user.id}")
            else:
                logger.warning(f"Failed to regenerate schedule ID {schedule_id}")
                flash('Could not regenerate schedule. Please try again or create a new one.', 'error')
                logger.info("Redirecting to /schedule due to regeneration failure")
                return redirect(url_for('schedule'))
        else:
            logger.warning(f"Invalid or unauthorized schedule ID {schedule_id} for user {current_user.id}")
            flash('Invalid schedule ID or unauthorized access. Please generate a new schedule.', 'error')
            logger.info("Redirecting to /schedule due to invalid schedule ID")
            return redirect(url_for('schedule'))

    if not schedule:
        logger.error(f"No schedule available for user {current_user.id}")
        flash('No schedule generated. Please select courses and try again.', 'error')
        logger.info("Redirecting to /schedule due to no schedule")
        return redirect(url_for('schedule'))

    logger.info(f"Displaying schedule for user {current_user.id}, schedule_id={schedule_id}")
    return render_template('schedule_result.html', schedule=schedule, schedule_id=schedule_id, time_to_minutes=time_to_minutes)

@app.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    logger.debug(f"Attempting to delete schedule ID {schedule_id} for user {current_user.id}")
    schedule = Schedule.query.get_or_404(schedule_id)
    if schedule.user_id != current_user.id:
        logger.warning(f"Unauthorized attempt to delete schedule ID {schedule_id} by user {current_user.id}")
        flash('Unauthorized action.', 'error')
        return redirect(url_for('saved_schedules'))
    db.session.delete(schedule)
    db.session.commit()
    logger.info(f"Schedule ID {schedule_id} deleted successfully by user {current_user.id}")
    flash(f'Schedule #{schedule_id} deleted successfully.', 'success')
    return redirect(url_for('saved_schedules'))

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
        logger.debug("Initializing database with mock courses")

        inserted = 0
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
                (10019, 'CS 171', 'Computer Programming I', '08:00AM', '09:00AM', 'Monday'),
                (10020, 'CS 171', 'Computer Programming I', '10:00AM', '11:00AM', 'Wednesday'),
                (10021, 'CS 171', 'Computer Programming I', '02:00PM', '03:00PM', 'Friday'),
                (10022, 'CS 175', 'Advanced Computer Programming I', '09:00AM', '10:00AM', 'Monday'),
                (10023, 'CS 175', 'Advanced Computer Programming I', '11:00AM', '12:00PM', 'Wednesday'),
                (10024, 'CS 175', 'Advanced Computer Programming I', '01:00PM', '02:00PM', 'Friday'),
                (10025, 'CS 172', 'Computer Programming II', '10:00AM', '11:00AM', 'Monday'),
                (10026, 'CS 172', 'Computer Programming II', '12:00PM', '01:00PM', 'Wednesday'),
                (10027, 'CS 172', 'Computer Programming II', '02:00PM', '03:00PM', 'Friday'),
                (10028, 'CS 260', 'Data Structures', '09:00AM', '10:00AM', 'Tuesday'),
                (10029, 'CS 260', 'Data Structures', '01:00PM', '02:00PM', 'Thursday'),
                (10030, 'CS 260', 'Data Structures', '03:00PM', '04:00PM', 'Friday'),
                (10031, 'CS 265', 'Advanced Programming Tools and Techniques', '08:00AM', '09:00AM', 'Tuesday'),
                (10032, 'CS 265', 'Advanced Programming Tools and Techniques', '10:00AM', '11:00AM', 'Thursday'),
                (10033, 'CS 265', 'Advanced Programming Tools and Techniques', '02:00PM', '03:00PM', 'Friday'),
                (10034, 'CS 270', 'Mathematical Foundations of Computer Science', '11:00AM', '12:00PM', 'Tuesday'),
                (10035, 'CS 270', 'Mathematical Foundations of Computer Science', '01:00PM', '02:00PM', 'Thursday'),
                (10036, 'CS 270', 'Mathematical Foundations of Computer Science', '03:00PM', '04:00PM', 'Friday'),
                (10037, 'CS 277', 'Algorithms and Analysis', '08:00AM', '09:00AM', 'Wednesday'),
                (10038, 'CS 277', 'Algorithms and Analysis', '10:00AM', '11:00AM', 'Thursday'),
                (10039, 'CS 277', 'Algorithms and Analysis', '02:00PM', '03:00PM', 'Friday'),
                (10040, 'CS 281', 'Systems Architecture', '09:00AM', '10:00AM', 'Tuesday'),
                (10041, 'CS 281', 'Systems Architecture', '01:00PM', '02:00PM', 'Thursday'),
                (10042, 'CS 281', 'Systems Architecture', '03:00PM', '04:00PM', 'Friday'),
                (10043, 'CS 283', 'Systems Programming', '08:00AM', '09:00AM', 'Monday'),
                (10044, 'CS 283', 'Systems Programming', '10:00AM', '11:00AM', 'Wednesday'),
                (10045, 'CS 283', 'Systems Programming', '02:00PM', '03:00PM', 'Friday'),
                (10046, 'CS 360', 'Programming Language Concepts', '09:00AM', '10:00AM', 'Tuesday'),
                (10047, 'CS 360', 'Programming Language Concepts', '11:00AM', '12:00PM', 'Thursday'),
                (10048, 'CS 360', 'Programming Language Concepts', '01:00PM', '02:00PM', 'Friday'),
                (10049, 'SE 181', 'Introduction to Software Engineering and Development', '08:00AM', '09:00AM', 'Monday'),
                (10050, 'SE 181', 'Introduction to Software Engineering and Development', '10:00AM', '11:00AM', 'Wednesday'),
                (10051, 'SE 181', 'Introduction to Software Engineering and Development', '01:00PM', '02:00PM', 'Friday'),
                (10052, 'SE 201', 'Introduction to Software Engineering and Development', '09:00AM', '10:00AM', 'Tuesday'),
                (10053, 'SE 201', 'Introduction to Software Engineering and Development', '11:00AM', '12:00PM', 'Thursday'),
                (10054, 'SE 201', 'Introduction to Software Engineering and Development', '01:00PM', '02:00PM', 'Friday'),
                (10055, 'SE 310', 'Software Architecture I', '08:00AM', '09:00AM', 'Monday'),
                (10056, 'SE 310', 'Software Architecture I', '10:00AM', '11:00AM', 'Wednesday'),
                (10057, 'SE 310', 'Software Architecture I', '02:00PM', '03:00PM', 'Friday'),
                (10058, 'COM 230', 'Techniques of Speaking', '09:00AM', '10:00AM', 'Monday'),
                (10059, 'COM 230', 'Techniques of Speaking', '11:00AM', '12:00PM', 'Wednesday'),
                (10060, 'COM 230', 'Techniques of Speaking', '02:00PM', '03:00PM', 'Friday'),
                (10061, 'ENGL 111', 'English Composition I', '08:00AM', '09:00AM', 'Tuesday'),
                (10062, 'ENGL 111', 'English Composition I', '10:00AM', '11:00AM', 'Thursday'),
                (10063, 'ENGL 111', 'English Composition I', '01:00PM', '02:00PM', 'Friday'),
                (10064, 'ENGL 112', 'Composition and Rhetoric II', '09:00AM', '10:00AM', 'Wednesday'),
                (10065, 'ENGL 112', 'Composition and Rhetoric II', '12:00PM', '01:00PM', 'Monday'),
                (10066, 'ENGL 112', 'Composition and Rhetoric II', '03:00PM', '04:00PM', 'Thursday'),
                (10067, 'ENGL 113', 'Composition and Rhetoric III', '08:00AM', '09:00AM', 'Friday'),
                (10068, 'ENGL 113', 'Composition and Rhetoric III', '11:00AM', '12:00PM', 'Tuesday'),
                (10069, 'ENGL 113', 'Composition and Rhetoric III', '02:00PM', '03:00PM', 'Monday'),
                (10070, 'PHIL 311', 'Ethics and Information Technology', '10:00AM', '11:00AM', 'Tuesday'),
                (10071, 'PHIL 311', 'Ethics and Information Technology', '01:00PM', '02:00PM', 'Wednesday'),
                (10072, 'PHIL 311', 'Ethics and Information Technology', '03:00PM', '04:00PM', 'Thursday'),
                (10073, 'ENGL 102', 'Composition and Rhetoric II', '08:00AM', '09:00AM', 'Monday'),
                (10074, 'ENGL 102', 'Composition and Rhetoric II', '10:00AM', '11:00AM', 'Wednesday'),
                (10075, 'ENGL 102', 'Composition and Rhetoric II', '02:00PM', '03:00PM', 'Tuesday'),
                (10076, 'ENGL 103', 'Composition and Rhetoric III', '09:00AM', '10:00AM', 'Thursday'),
                (10077, 'ENGL 103', 'Composition and Rhetoric III', '12:00PM', '01:00PM', 'Wednesday'),
                (10078, 'ENGL 103', 'Composition and Rhetoric III', '03:00PM', '04:00PM', 'Monday'),
                (10079, 'CI 101', 'Computing and Informatics Design I', '08:00AM', '9:00AM', 'Monday'),
                (10080, 'CI 101', 'Computing and Informatics Design I', '01:00PM', '02:00PM', 'Wednesday'),
                (10081, 'CI 101', 'Computing and Informatics Design I', '09:00AM', '10:00AM', 'Friday'),
                (10082, 'CI 102', 'Computing and Informatics Design II', '10:00AM', '11:00PM', 'Monday'),
                (10083, 'CI 102', 'Computing and Informatics Design II', '02:00PM', '03:00PM', 'Wednesday'),
                (10084, 'CI 102', 'Computing and Informatics Design II', '11:00AM', '12:00PM', 'Friday'),
                (10085, 'CI 103', 'Computing and Informatics Design III', '08:00AM', '9:00AM', 'Tuesday'),
                (10086, 'CI 103', 'Computing and Informatics Design III', '01:00PM', '02:00PM', 'Thursday'),
                (10087, 'CI 103', 'Computing and Informatics Design III', '09:00AM', '10:00AM', 'Friday'),
                (10088, 'CI 491 [WI]', 'Senior Project I', '10:00AM', '11:00AM', 'Monday'),
                (10089, 'CI 491 [WI]', 'Senior Project I', '02:00PM', '03:00PM', 'Wednesday'),
                (10090, 'CI 491 [WI]', 'Senior Project I', '01:00PM', '02:00PM', 'Friday'),
                (10091, 'CI 492 [WI]', 'Senior Project II', '08:00AM', '09:00AM', 'Tuesday'),
                (10092, 'CI 492 [WI]', 'Senior Project II', '01:00PM', '02:00PM', 'Thursday'),
                (10093, 'CI 492 [WI]', 'Senior Project II', '09:00AM', '10:00PM', 'Friday'),
                (10094, 'CI 493 [WI]', 'Senior Project III', '10:00AM', '11:00AM', 'Monday'),
                (10095, 'CI 493 [WI]', 'Senior Project III', '02:00PM', '03:00PM', 'Wednesday'),
                (10096, 'CI 493 [WI]', 'Senior Project III', '01:00PM', '02:00PM', 'Friday'),
                10097, ('CI 101', 'The Drexel Experience', '09:00AM', '10:00AM', 'Monday'),
                10098, ('CI 120', 'CCI Transfer Student Seminar', '11:00AM', '12:00PM', 'Wednesday'),
                10099, ('CIVC 101', 'Introduction to Civic Engagement', '02:00PM', '03:00PM', 'Friday'),
                10100, ('COOP 101', 'Career Management and Professional Development **', '10:00AM', '11:00AM', 'Tuesday'),
            ]
        
            for course in mock_courses:
                if not Course.query.filter_by(crn=course[0]).first():
                    db.session.add(Course(crn=course[0], course_code=course[1], course_name=course[2],
                                         start_time=course[3], end_time=course[4], day=course[5]))
                    inserted += 1
        db.session.commit()
        logger.info(f"Database initialized with {inserted} new courses")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)