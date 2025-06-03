from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import logging
import os
import base64
from sqlalchemy import text

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
    course1 = db.Column(db.String(100))
    course2 = db.Column(db.String(100))
    course3 = db.Column(db.String(100))
    course4 = db.Column(db.String(100))
    course5 = db.Column(db.String(100))
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    spacing = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_favorite = db.Column(db.Boolean, default=False)
    is_priority = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Time conversion utilities
def time_to_minutes(time_str):
    if not time_str:
        return None
    # Normalize spaces and case, remove AM/PM for processing
    time_str = time_str.strip().replace(" ", "").upper()
    try:
        # Handle formats like "8:00AM", "08:00AM", "8AM"
        if ':' not in time_str:
            time_str = time_str.replace("AM", ":00AM").replace("PM", ":00PM")
        hour, minute = map(int, time_str.replace("AM", "").replace("PM", "").split(':'))
        if time_str.endswith("PM") and hour != 12:
            hour += 12
        elif time_str.endswith("AM") and hour == 12:
            hour = 0
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
        flash('Invalid time range selected.', 'error')
        return None

    # Get all course instances
    all_courses = Course.query.filter(Course.course_code.in_(courses_selected)).all()
    logger.debug(f"Found {len(all_courses)} courses: {[c.course_code + ' ' + c.start_time + '-' + c.end_time + ' ' + c.day for c in all_courses]}")
    if not all_courses:
        logger.error(f"No courses found for {courses_selected}")
        flash(f'No sections available for courses: {", ".join(courses_selected)}.', 'error')
        return None

    # Filter courses (include if any part of the course falls within the range)
    filtered_courses = []
    for course in all_courses:
        course_start = time_to_minutes(course.start_time)
        course_end = time_to_minutes(course.end_time)
        if course_start is None or course_end is None:
            logger.warning(f"Invalid time for course {course.course_code}: {course.start_time}-{course.end_time}")
            continue
        # Include courses that start or end within the range, or span it
        if (course_start <= end_minutes and course_end >= start_minutes):
            filtered_courses.append(course)
            logger.debug(f"Added course {course.course_code} ({course.start_time}-{course.end_time}, {course.day}) to filtered list")

    logger.debug(f"Filtered {len(filtered_courses)} courses within {start_time}-{end_time}")
    if not filtered_courses:
        logger.error(f"No courses available within time range {start_time}-{end_time}")
        flash(f'No courses available between {start_time} and {end_time} for selected courses.', 'error')
        return None

    # Group by course code
    course_options = {}
    for course in filtered_courses:
        if course.course_code not in course_options:
            course_options[course.course_code] = []
        course_options[course.course_code].append(course)
    logger.debug(f"Course options: {course_options.keys()}")

    # Check if all selected courses have options
    missing_courses = [code for code in courses_selected if code not in course_options]
    if missing_courses:
        logger.error(f"No sections available for courses: {missing_courses}")
        flash(f'No sections available for courses: {", ".join(missing_courses)}.', 'error')
        return None

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
                logger.debug(f"Skipping course {course.course_code} due to invalid times")
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
                    if used_end < start and start - used_end < 15:  # 15-minute gap
                        conflict = True
                        break
                    if end < used_start and used_start - end < 15:  # 15-minute gap
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

    # Try with specified spacing
    schedule = backtrack([], {}, courses_selected)
    if not schedule and spacing == "spaced-out":
        logger.info(f"Retrying with compact spacing for {courses_selected}")
        # Retry with compact spacing as a fallback
        schedule = backtrack([], {}, courses_selected)  # spacing is ignored in backtrack for compact
    if not schedule:
        logger.error(f"Failed to generate schedule for {courses_selected} with spacing={spacing}")
        flash('Could not generate a schedule. Try fewer courses, a wider time range, or compact spacing.', 'error')
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
    # Fetch distinct courses by course_code, selecting the first course_name and credits for each
    courses = db.session.query(Course.course_code, Course.course_name, Course.credits)\
                       .group_by(Course.course_code)\
                       .order_by(Course.course_code).all()
    # Convert the result into a list of objects with course_code, course_name, and credits
    class CourseObj:
        def __init__(self, course_code, course_name, credits):
            self.course_code = course_code
            self.course_name = course_name
            self.credits = credits if credits is not None else 3  # Default to 3 if credits is None
    courses = [CourseObj(course[0], course[1], course[2]) for course in courses]
    logger.debug(f"Fetched {len(courses)} courses for schedule: {[c.course_code for c in courses]}")
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
            if course.strip():  # Only add non-empty courses
                courses_selected.append(course.strip())
            i += 1

        if not courses_selected:
            logger.error("No valid courses selected")
            flash('Please select at least one valid course.', 'error')
            return redirect(url_for('schedule'))

        # Get time and spacing preferences
        start_time = request.form.get('startTime')
        end_time = request.form.get('endTime')
        spacing = request.form.get('spacing', 'compact')  # Default to compact if missing

        # Validate inputs
        if not start_time or not end_time:
            logger.error(f"Missing time preferences: startTime={start_time}, endTime={end_time}")
            flash('Please select start and end times.', 'error')
            return redirect(url_for('schedule'))

        # Calculate total credits for unique courses
        unique_courses = list(set(courses_selected))
        # Use a query to get one instance per course code
        course_credits = db.session.query(Course.course_code, Course.credits).filter(Course.course_code.in_(unique_courses)).group_by(Course.course_code).all()
        total_credits = sum(course.credits for course in course_credits)
        logger.debug(f"Total credits for {unique_courses}: {total_credits} (Courses: {[f'{c.course_code}: {c.credits}' for c in course_credits]})")

        # Validate credit limit
        if total_credits > 20:
            logger.error(f"Total credits ({total_credits}) exceed 20")
            flash(f'Total credits ({total_credits}) exceed 20. Please select fewer courses. (Selected: {", ".join(unique_courses)})', 'error')
            return redirect(url_for('schedule'))

        # Validate time range
        start_minutes = time_to_minutes(start_time)
        end_minutes = time_to_minutes(end_time)
        if start_minutes is None or end_minutes is None:
            logger.error(f"Invalid time format: startTime={start_time}, endTime={end_time}")
            flash('Invalid time format. Please use HH:MM AM/PM.', 'error')
            return redirect(url_for('schedule'))
        if start_minutes >= end_minutes:
            logger.error(f"End time before start time: {start_time} >= {end_time}")
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
            session['total_credits'] = total_credits
            logger.info(f"Schedule generated successfully for user {current_user.id}")
            flash('Schedule generated successfully! Save it to keep it.', 'success')
            return redirect(url_for('display_schedule'))
        else:
            logger.error(f"Failed to generate schedule for {courses_selected}")
            flash('Could not generate a conflict-free schedule. Try fewer courses, a wider time range, or compact spacing.', 'error')
            return redirect(url_for('schedule'))
    except Exception as e:
        logger.error(f"Unexpected error in save_schedule for user {current_user.id}: {e}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('schedule'))

@app.route('/save_variant', methods=['POST'])
@login_required
def save_variant():
    try:
        schedule = session.get('schedule')
        if not schedule:
            logger.error(f"No schedule to save as variant for user {current_user.id}")
            flash('No schedule to save as variant.', 'error')
            return jsonify({'success': False, 'message': 'No schedule to save.'}), 400

        # Initialize or retrieve schedule_variants
        if 'schedule_variants' not in session:
            session['schedule_variants'] = []
        
        # Check if max variants reached
        if len(session['schedule_variants']) >= 3:
            logger.debug(f"Max variants (3) reached for user {current_user.id}")
            flash('Maximum 3 variants saved. Generate a new schedule to replace one.', 'error')
            return jsonify({'success': False, 'message': 'Maximum 3 variants saved.'}), 400

        # Append schedule to variants
        session['schedule_variants'].append(schedule)
        variant_number = len(session['schedule_variants'])
        session.modified = True
        logger.info(f"Schedule saved as variant {variant_number} for user {current_user.id}")
        flash(f'Schedule saved as variant {variant_number}', 'success')
        return jsonify({'success': True, 'message': f'Schedule saved as variant {variant_number}'}), 200
    except Exception as e:
        logger.error(f"Error saving variant for user {current_user.id}: {str(e)}")
        flash('Error saving variant. Please try again.', 'error')
        return jsonify({'success': False, 'message': 'Error saving variant.'}), 500

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

    course_dict = {f'course{i+1}': courses_selected[i] if i < len(courses_selected) else None for i in range(5)}

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

    # Save the schedule ID to session for comparison
    if 'compare_schedules' not in session:
        session['schedule_comparison'] = []
    
    session['schedule_comparison'].append(new_schedule.id)
    session.modified = True

    return jsonify({'success': True, 'message': f'Schedule #{new_schedule.id} saved successfully!'}), 200


@app.route('/saved_schedules')
@login_required
def saved_schedules():
    try:
        # Check if is_favorite and is_priority columns exist
        conn = db.engine.connect()
        result = conn.execute(text("PRAGMA table_info(schedule)")).fetchall()
        columns = [row[1] for row in result]
        conn.close()
        
        # Initialize base query
        query = Schedule.query.filter_by(user_id=current_user.id)
        
        # Add search functionality
        search_query = request.args.get('search', '').strip()
        if search_query:
            query = query.filter(
                or_(
                    Schedule.course1.ilike(f'%{search_query}%'),
                    Schedule.course2.ilike(f'%{search_query}%'),
                    Schedule.course3.ilike(f'%{search_query}%'),
                    Schedule.course4.ilike(f'%{search_query}%'),
                    Schedule.course5.ilike(f'%{search_query}%')
                )
            )
        
        # Apply sorting based on priority, favorite, and creation date
        if 'is_favorite' not in columns or 'is_priority' not in columns:
            logger.error("is_favorite or is_priority column missing in schedule table")
            flash('Priority and favorite features unavailable. Please contact support.', 'error')
            schedules = query.order_by(Schedule.created_at.desc()).all()
        else:
            schedules = query.order_by(
                Schedule.is_priority.desc(),
                Schedule.is_favorite.desc(),
                Schedule.created_at.desc()
            ).all()
        
        # Calculate total credits for each schedule
        schedules_with_credits = []
        for schedule in schedules:
            # Extract courses from the schedule (remove None values)
            courses = [course for course in [
                schedule.course1, schedule.course2, schedule.course3,
                schedule.course4, schedule.course5
            ] if course]
            # Get unique course codes
            unique_courses = list(set(courses))
            # Query credits for these courses
            course_credits = Course.query.filter(Course.course_code.in_(unique_courses)).group_by(Course.course_code).all()
            total_credits = sum(course.credits for course in course_credits) if course_credits else 0
            # Create a dictionary to pass to the template
            schedule_dict = {
                'id': schedule.id,
                'courses': courses,
                'start_time': schedule.start_time,
                'end_time': schedule.end_time,
                'spacing': schedule.spacing,
                'created_at': schedule.created_at,
                'is_favorite': schedule.is_favorite,
                'is_priority': schedule.is_priority,
                'total_credits': total_credits  # Add total credits to the schedule data
            }
            schedules_with_credits.append(schedule_dict)
        
        return render_template('saved_schedules.html', schedules=schedules_with_credits, current_time=datetime.now().strftime('%I:%M %p %Z'))
    except Exception as e:
        logger.error(f"Error fetching saved schedules for user {current_user.id}: {str(e)}")
        flash('Error loading saved schedules. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    
@app.route('/compare_schedules', methods=['GET'])
@login_required
def compare_schedules():
    try:
        # Get the schedules to compare from session
        compare_schedules = session.get('compare_schedules', [])
        
        if not compare_schedules:
            flash('No schedules selected for comparison.', 'error')
            return redirect(url_for('saved_schedules'))

        # Fetch course data for each schedule and calculate total credits
        schedules_with_details = []
        for schedule_id in compare_schedules:
            schedule = Schedule.query.get(schedule_id)
            if schedule and schedule.user_id == current_user.id:
                # Extract courses from the schedule (remove None values)
                courses = [course for course in [
                    schedule.course1, schedule.course2, schedule.course3,
                    schedule.course4, schedule.course5
                ] if course]
                
                # Get unique course codes
                unique_courses = list(set(courses))
                # Query credits for these courses
                course_credits = Course.query.filter(Course.course_code.in_(unique_courses)).group_by(Course.course_code).all()
                total_credits = sum(course.credits for course in course_credits) if course_credits else 0

                schedule_dict = {
                    'id': schedule.id,
                    'courses': courses,
                    'start_time': schedule.start_time,
                    'end_time': schedule.end_time,
                    'spacing': schedule.spacing,
                    'created_at': schedule.created_at,
                    'total_credits': total_credits
                }
                schedules_with_details.append(schedule_dict)
        
        return render_template('schedule_comparison.html', schedules=schedules_with_details)

    except Exception as e:
        logger.error(f"Error comparing schedules for user {current_user.id}: {str(e)}")
        flash('Error comparing schedules. Please try again.', 'error')
        return redirect(url_for('saved_schedules'))
    
@app.route('/admin/add_course', methods=['GET', 'POST'])
@login_required
def add_course():
    if request.method == 'POST':
        try:
            course = Course(
                crn=request.form['crn'],
                course_code=request.form['course_code'],
                course_name=request.form['course_name'],
                start_time=request.form['start_time'],
                end_time=request.form['end_time'],
                day=request.form['day']
            )
            db.session.add(course)
            db.session.commit()
            flash('Course added successfully!', 'success')
            logger.info(f"Added course: {course.course_code} - {course.course_name}")
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding course: {str(e)}', 'error')
            logger.error(f"Failed to add course: {str(e)}")
        return redirect(url_for('add_course'))
    return render_template('add_course.html')

@app.route('/toggle_favorite/<int:schedule_id>', methods=['POST'])
@login_required
def toggle_favorite(schedule_id):
    logger.debug(f"Attempting to toggle favorite for schedule ID {schedule_id} for user {current_user.id}")
    schedule = Schedule.query.get_or_404(schedule_id)
    if schedule.user_id != current_user.id:
        logger.warning(f"Unauthorized attempt to toggle favorite for schedule ID {schedule_id} by user {current_user.id}")
        return jsonify({'success': False, 'message': 'Unauthorized action.'}), 403
    schedule.is_favorite = not schedule.is_favorite
    db.session.commit()
    logger.info(f"Schedule ID {schedule_id} favorite status set to {schedule.is_favorite} by user {current_user.id}")
    return jsonify({'success': True, 'message': f'Schedule #{schedule_id} {"favorited" if schedule.is_favorite else "unfavorited"}.', 'is_favorite': schedule.is_favorite}), 200

@app.route('/set_priority/<int:schedule_id>', methods=['POST'])
@login_required
def set_priority(schedule_id):
    logger.debug(f"Attempting to set priority for schedule ID {schedule_id} for user {current_user.id}")
    schedule = Schedule.query.get_or_404(schedule_id)
    if schedule.user_id != current_user.id:
        logger.warning(f"Unauthorized attempt to set priority for schedule ID {schedule_id} by user {current_user.id}")
        return jsonify({'success': False, 'message': 'Unauthorized action.'}), 403
    
    try:
        # Clear existing priority for this user
        Schedule.query.filter_by(user_id=current_user.id, is_priority=True).update({'is_priority': False})
        
        # Set new priority
        schedule.is_priority = True
        db.session.commit()
        logger.info(f"Schedule ID {schedule_id} set as priority for user {current_user.id}")
        return jsonify({'success': True, 'message': f'Schedule #{schedule_id} set as priority.', 'is_priority': True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error setting priority for schedule ID {schedule_id}: {str(e)}")
        return jsonify({'success': False, 'message': f'Error setting priority: {str(e)}'}), 500
    
@app.route('/display_schedule')
@login_required
def display_schedule():
    logger.debug(f"Accessing display_schedule for user {current_user.id}, session: {session}, args: {request.args}")
    schedule_id = request.args.get('schedule_id', session.get('schedule_id'), type=int)
    logger.debug(f"Schedule ID: {schedule_id}, source: {'request.args' if request.args.get('schedule_id') else 'session' if session.get('schedule_id') else 'none'}")
    schedule = session.get('schedule', [])
    total_credits = 0
    courses_selected = session.get('courses_selected', [])

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
                # Calculate total credits
                unique_courses = list(set(courses_selected))
                course_credits = Course.query.filter(Course.course_code.in_(unique_courses)).group_by(Course.course_code).all()
                total_credits = sum(course.credits for course in course_credits)
                logger.debug(f"Calculated total credits: {total_credits}")
                session['total_credits'] = total_credits
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
    else:
        # If no schedule_id, get total credits from session and courses
        if courses_selected:
            unique_courses = list(set(courses_selected))
            course_credits = Course.query.filter(Course.course_code.in_(unique_courses)).group_by(Course.course_code).all()
            total_credits = sum(course.credits for course in course_credits)
            logger.debug(f"Calculated total credits from session: {total_credits}")
        else:
            total_credits = session.get('total_credits', 0)
            logger.debug(f"Got total credits from session: {total_credits}")

    if not schedule:
        logger.error(f"No schedule available for user {current_user.id}")
        flash('No schedule generated. Please select courses and try again.', 'error')
        logger.info("Redirecting to /schedule due to no schedule")
        return redirect(url_for('schedule'))

    logger.info(f"Displaying schedule for user {current_user.id}, schedule_id={schedule_id}, total_credits={total_credits}")
    return render_template('schedule_result.html', schedule=schedule, schedule_id=schedule_id, time_to_minutes=time_to_minutes, total_credits=total_credits)

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

@app.route('/courses')
@login_required
def courses():
    courses = db.session.query(Course.course_code, Course.course_name, Course.credits)\
                       .group_by(Course.course_code)\
                       .order_by(Course.course_code).all()
    class CourseObj:
        def __init__(self, course_code, course_name, credits):
            self.course_code = course_code
            self.course_name = course_name
            self.credits = credits if credits is not None else 3
    courses = [CourseObj(course[0], course[1], course[2]) for course in courses]
    logger.debug(f"Courses fetched: {[course.course_code for course in courses]}")
    return render_template('courses.html', user=current_user, courses=courses)

@app.route('/about')
def about():
    return render_template('about.html')

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
                (10001, 'CS 164', 'Intro to Computer Science', '08:00AM', '09:00AM', 'Monday', 3),
                (10002, 'CS 164', 'Intro to Computer Science', '10:00AM', '11:00AM', 'Wednesday', 3),
                (10003, 'CS 164', 'Intro to Computer Science', '02:00PM', '03:00PM', 'Friday', 3),
                (10004, 'MATH 121', 'Calculus I', '09:00AM', '10:00AM', 'Tuesday', 4),
                (10005, 'MATH 121', 'Calculus I', '11:00AM', '12:00PM', 'Thursday', 4),
                (10006, 'MATH 121', 'Calculus I', '01:00PM', '02:00PM', 'Monday', 4),
                (10007, 'ENGL 101', 'Composition and Rhetoric I', '10:00AM', '11:00AM', 'Monday', 3),
                (10008, 'ENGL 101', 'Composition and Rhetoric I', '01:00PM', '02:00PM', 'Wednesday', 3),
                (10009, 'ENGL 101', 'Composition and Rhetoric I', '03:00PM', '04:00PM', 'Friday', 3),
                (10010, 'CHEM 101', 'General Chemistry I', '08:00AM', '09:00AM', 'Thursday', 4),
                (10011, 'CHEM 101', 'General Chemistry I', '12:00PM', '01:00PM', 'Tuesday', 4),
                (10012, 'CHEM 101', 'General Chemistry I', '02:00PM', '03:00PM', 'Wednesday', 4),
                (10013, 'COOP 101', 'Career Management', '09:00AM', '10:00AM', 'Friday', 3),
                (10014, 'COOP 101', 'Career Management', '11:00AM', '12:00PM', 'Monday', 3),
                (10015, 'COOP 101', 'Career Management', '03:00PM', '04:00PM', 'Tuesday', 3),
                (10016, 'UNIV 101', 'The Drexel Experience', '08:00AM', '09:00AM', 'Wednesday', 3),
                (10017, 'UNIV 101', 'The Drexel Experience', '12:00PM', '01:00PM', 'Friday', 3),
                (10018, 'UNIV 101', 'The Drexel Experience', '01:00PM', '02:00PM', 'Thursday', 3),
                (10019, 'CS 171', 'Computer Programming I', '08:00AM', '09:00AM', 'Monday', 4),
                (10020, 'CS 171', 'Computer Programming I', '10:00AM', '11:00AM', 'Wednesday', 4),
                (10021, 'CS 171', 'Computer Programming I', '02:00PM', '03:00PM', 'Friday', 4),
                (10022, 'CS 175', 'Advanced Computer Programming I', '09:00AM', '10:00AM', 'Monday', 4),
                (10023, 'CS 175', 'Advanced Computer Programming I', '11:00AM', '12:00PM', 'Wednesday', 4),
                (10024, 'CS 175', 'Advanced Computer Programming I', '01:00PM', '02:00PM', 'Friday', 4),
                (10025, 'CS 172', 'Computer Programming II', '10:00AM', '11:00AM', 'Monday', 4),
                (10026, 'CS 172', 'Computer Programming II', '12:00PM', '01:00PM', 'Wednesday', 4),
                (10027, 'CS 172', 'Computer Programming II', '02:00PM', '03:00PM', 'Friday', 4),
                (10028, 'CS 260', 'Data Structures', '09:00AM', '10:00AM', 'Tuesday', 4),
                (10029, 'CS 260', 'Data Structures', '01:00PM', '02:00PM', 'Thursday', 4),
                (10030, 'CS 260', 'Data Structures', '03:00PM', '04:00PM', 'Friday', 4),
                (10031, 'CS 265', 'Advanced Programming Tools and Techniques', '08:00AM', '09:00AM', 'Tuesday', 4),
                (10032, 'CS 265', 'Advanced Programming Tools and Techniques', '10:00AM', '11:00AM', 'Thursday', 4),
                (10033, 'CS 265', 'Advanced Programming Tools and Techniques', '02:00PM', '03:00PM', 'Friday', 4),
                (10034, 'CS 270', 'Mathematical Foundations of Computer Science', '11:00AM', '12:00PM', 'Tuesday', 3),
                (10035, 'CS 270', 'Mathematical Foundations of Computer Science', '01:00PM', '02:00PM', 'Thursday', 3),
                (10036, 'CS 270', 'Mathematical Foundations of Computer Science', '03:00PM', '04:00PM', 'Friday', 3),
                (10037, 'CS 277', 'Algorithms and Analysis', '08:00AM', '09:00AM', 'Wednesday', 3),
                (10038, 'CS 277', 'Algorithms and Analysis', '10:00AM', '11:00AM', 'Thursday', 3),
                (10039, 'CS 277', 'Algorithms and Analysis', '02:00PM', '03:00PM', 'Friday', 3),
                (10040, 'CS 281', 'Systems Architecture', '09:00AM', '10:00AM', 'Tuesday', 3),
                (10041, 'CS 281', 'Systems Architecture', '01:00PM', '02:00PM', 'Thursday', 3),
                (10042, 'CS 281', 'Systems Architecture', '03:00PM', '04:00PM', 'Friday', 3),
                (10043, 'CS 283', 'Systems Programming', '08:00AM', '09:00AM', 'Monday', 3),
                (10044, 'CS 283', 'Systems Programming', '10:00AM', '11:00AM', 'Wednesday', 3),
                (10045, 'CS 283', 'Systems Programming', '02:00PM', '03:00PM', 'Friday', 3),
                (10046, 'CS 360', 'Programming Language Concepts', '09:00AM', '10:00AM', 'Tuesday', 3),
                (10047, 'CS 360', 'Programming Language Concepts', '11:00AM', '12:00PM', 'Thursday', 3),
                (10048, 'CS 360', 'Programming Language Concepts', '01:00PM', '02:00PM', 'Friday', 3),
                (10049, 'SE 181', 'Introduction to Software Engineering and Development', '08:00AM', '09:00AM', 'Monday', 3),
                (10050, 'SE 181', 'Introduction to Software Engineering and Development', '10:00AM', '11:00AM', 'Wednesday', 3),
                (10051, 'SE 181', 'Introduction to Software Engineering and Development', '01:00PM', '02:00PM', 'Friday', 3),
                (10052, 'SE 201', 'Introduction to Software Engineering and Development', '09:00AM', '10:00AM', 'Tuesday', 4),
                (10053, 'SE 201', 'Introduction to Software Engineering and Development', '11:00AM', '12:00PM', 'Thursday', 4),
                (10054, 'SE 201', 'Introduction to Software Engineering and Development', '01:00PM', '02:00PM', 'Friday', 4),
                (10055, 'SE 310', 'Software Architecture I', '08:00AM', '09:00AM', 'Monday', 4),
                (10056, 'SE 310', 'Software Architecture I', '10:00AM', '11:00AM', 'Wednesday', 4),
                (10057, 'SE 310', 'Software Architecture I', '02:00PM', '03:00PM', 'Friday', 4),
                (10058, 'COM 230', 'Techniques of Speaking', '09:00AM', '10:00AM', 'Monday', 3),
                (10059, 'COM 230', 'Techniques of Speaking', '11:00AM', '12:00PM', 'Wednesday', 3),
                (10060, 'COM 230', 'Techniques of Speaking', '02:00PM', '03:00PM', 'Friday', 3),
                (10061, 'ENGL 111', 'English Composition I', '08:00AM', '09:00AM', 'Tuesday', 3),
                (10062, 'ENGL 111', 'English Composition I', '10:00AM', '11:00AM', 'Thursday', 3),
                (10063, 'ENGL 111', 'English Composition I', '01:00PM', '02:00PM', 'Friday', 3),
                (10064, 'ENGL 112', 'Composition and Rhetoric II', '09:00AM', '10:00AM', 'Wednesday', 3),
                (10065, 'ENGL 112', 'Composition and Rhetoric II', '12:00PM', '01:00PM', 'Monday', 3),
                (10066, 'ENGL 112', 'Composition and Rhetoric II', '03:00PM', '04:00PM', 'Thursday', 3),
                (10067, 'ENGL 113', 'Composition and Rhetoric III', '08:00AM', '09:00AM', 'Friday', 3),
                (10068, 'ENGL 113', 'Composition and Rhetoric III', '11:00AM', '12:00PM', 'Tuesday', 3),
                (10069, 'ENGL 113', 'Composition and Rhetoric III', '02:00PM', '03:00PM', 'Monday', 3),
                (10070, 'PHIL 311', 'Ethics and Information Technology', '10:00AM', '11:00AM', 'Tuesday', 4),
                (10071, 'PHIL 311', 'Ethics and Information Technology', '01:00PM', '02:00PM', 'Wednesday', 4),
                (10072, 'PHIL 311', 'Ethics and Information Technology', '03:00PM', '04:00PM', 'Thursday', 4),
                (10073, 'ENGL 102', 'Composition and Rhetoric II', '08:00AM', '09:00AM', 'Monday', 3),
                (10074, 'ENGL 102', 'Composition and Rhetoric II', '10:00AM', '11:00AM', 'Wednesday', 3),
                (10075, 'ENGL 102', 'Composition and Rhetoric II', '02:00PM', '03:00PM', 'Tuesday', 3),
                (10076, 'ENGL 103', 'Composition and Rhetoric III', '09:00AM', '10:00AM', 'Thursday', 3),
                (10077, 'ENGL 103', 'Composition and Rhetoric III', '12:00PM', '01:00PM', 'Wednesday', 3),
                (10078, 'ENGL 103', 'Composition and Rhetoric III', '03:00PM', '04:00PM', 'Monday', 3),
                (10079, 'CI 101', 'Computing and Informatics Design I', '08:00AM', '09:00AM', 'Monday', 3),
                (10080, 'CI 101', 'Computing and Informatics Design I', '01:00PM', '02:00PM', 'Wednesday', 3),
                (10081, 'CI 101', 'Computing and Informatics Design I', '09:00AM', '10:00AM', 'Friday', 3),
                (10082, 'CI 102', 'Computing and Informatics Design II', '10:00AM', '11:00AM', 'Monday', 3),
                (10083, 'CI 102', 'Computing and Informatics Design II', '02:00PM', '03:00PM', 'Wednesday', 3),
                (10084, 'CI 102', 'Computing and Informatics Design II', '11:00AM', '12:00PM', 'Friday', 3),
                (10085, 'CI 103', 'Computing and Informatics Design III', '08:00AM', '09:00AM', 'Tuesday', 3),
                (10086, 'CI 103', 'Computing and Informatics Design III', '01:00PM', '02:00PM', 'Thursday', 3),
                (10087, 'CI 103', 'Computing and Informatics Design III', '09:00AM', '10:00AM', 'Friday', 3),
                (10088, 'CI 491 [WI]', 'Senior Project I', '10:00AM', '11:00AM', 'Monday', 4),
                (10089, 'CI 491 [WI]', 'Senior Project I', '02:00PM', '03:00PM', 'Wednesday', 4),
                (10090, 'CI 491 [WI]', 'Senior Project I', '01:00PM', '02:00PM', 'Friday', 4),
                (10091, 'CI 492 [WI]', 'Senior Project II', '08:00AM', '09:00AM', 'Tuesday', 4),
                (10092, 'CI 492 [WI]', 'Senior Project II', '01:00PM', '02:00PM', 'Thursday', 4),
                (10093, 'CI 492 [WI]', 'Senior Project II', '09:00AM', '10:00AM', 'Friday', 4),
                (10094, 'CI 493 [WI]', 'Senior Project III', '10:00AM', '11:00AM', 'Monday', 4),
                (10095, 'CI 493 [WI]', 'Senior Project III', '02:00PM', '03:00PM', 'Wednesday', 4),
                (10096, 'CI 493 [WI]', 'Senior Project III', '01:00PM', '02:00PM', 'Friday', 4),
                # BIO 131 - Cells and Biomolecules (1-hour lectures)
                (10097, 'BIO 131', 'Cells and Biomolecules', '09:00AM', '10:00AM', 'Monday', 3),
                (10098, 'BIO 131', 'Cells and Biomolecules', '11:00AM', '12:00PM', 'Wednesday', 3),
                (10099, 'BIO 131', 'Cells and Biomolecules', '02:00PM', '03:00PM', 'Friday', 3),

                # BIO 134 - Cells and Biomolecules Lab (2-hour labs)
                (10100, 'BIO 134', 'Cells and Biomolecules Lab', '08:00AM', '10:00AM', 'Tuesday',2),
                (10101, 'BIO 134', 'Cells and Biomolecules Lab', '01:00PM', '03:00PM', 'Thursday',2),
                (10102, 'BIO 134', 'Cells and Biomolecules Lab', '10:00AM', '12:00PM', 'Friday',2),

                # BIO 132 - Genetics and Evolution (1-hour lectures)
                (10103, 'BIO 132', 'Genetics and Evolution', '10:00AM', '11:00AM', 'Tuesday', 3),
                (10104, 'BIO 132', 'Genetics and Evolution', '12:00PM', '01:00PM', 'Thursday', 3),
                (10105, 'BIO 132', 'Genetics and Evolution', '03:00PM', '04:00PM', 'Monday', 3),

                # BIO 135 - Genetics and Evolution Lab (2-hour labs)
                (10106, 'BIO 135', 'Genetics and Evolution Lab', '09:00AM', '11:00AM', 'Wednesday',2),
                (10107, 'BIO 135', 'Genetics and Evolution Lab', '02:00PM', '04:00PM', 'Tuesday',2),
                (10108, 'BIO 135', 'Genetics and Evolution Lab', '11:00AM', '01:00PM', 'Friday',2),

                # BIO 133 - Physiology and Ecology (1-hour lectures)
                (10109, 'BIO 133', 'Physiology and Ecology', '08:00AM', '09:00AM', 'Friday', 3),
                (10110, 'BIO 133', 'Physiology and Ecology', '01:00PM', '02:00PM', 'Wednesday', 3),
                (10111, 'BIO 133', 'Physiology and Ecology', '10:00AM', '11:00AM', 'Tuesday', 3),

                # BIO 136 - Anatomy and Ecology Lab (2-hour labs)
                (10112, 'BIO 136', 'Anatomy and Ecology Lab', '10:00AM', '12:00PM', 'Monday',2),
                (10113, 'BIO 136', 'Anatomy and Ecology Lab', '02:00PM', '04:00PM', 'Thursday',2),
                (10114, 'BIO 136', 'Anatomy and Ecology Lab', '08:00AM', '10:00AM', 'Wednesday',2),

                # CHEM 102 - General Chemistry II (1-hour lectures)
                (10115, 'CHEM 102', 'General Chemistry II', '09:00AM', '10:00AM', 'Thursday', 3),
                (10116, 'CHEM 102', 'General Chemistry II', '11:00AM', '12:00PM', 'Tuesday', 3),
                (10117, 'CHEM 102', 'General Chemistry II', '01:00PM', '02:00PM', 'Friday', 3),

                # CHEM 103 - General Chemistry III (1-hour lectures)
                (10118, 'CHEM 103', 'General Chemistry III', '08:00AM', '09:00AM', 'Monday', 3),
                (10119, 'CHEM 103', 'General Chemistry III', '12:00PM', '01:00PM', 'Wednesday', 3),
                (10120, 'CHEM 103', 'General Chemistry III', '02:00PM', '03:00PM', 'Tuesday', 3),

                # PHYS 101 - Fundamentals of Physics I (1-hour lectures)
                (10121, 'PHYS 101', 'Fundamentals of Physics I', '10:00AM', '11:00AM', 'Friday', 3),
                (10122, 'PHYS 101', 'Fundamentals of Physics I', '01:00PM', '02:00PM', 'Monday', 3),
                (10123, 'PHYS 101', 'Fundamentals of Physics I', '03:00PM', '04:00PM', 'Wednesday', 3),

                # PHYS 102 - Fundamentals of Physics II (1-hour lectures)
                (10124, 'PHYS 102', 'Fundamentals of Physics II', '09:00AM', '10:00AM', 'Tuesday', 3),
                (10125, 'PHYS 102', 'Fundamentals of Physics II', '11:00AM', '12:00PM', 'Thursday', 3),
                (10126, 'PHYS 102', 'Fundamentals of Physics II', '02:00PM', '03:00PM', 'Monday', 3),

                # PHYS 201 - Fundamentals of Physics III (1-hour lectures)
                (10127, 'PHYS 201', 'Fundamentals of Physics III', '08:00AM', '09:00AM', 'Wednesday', 3),
                (10128, 'PHYS 201', 'Fundamentals of Physics III', '12:00PM', '01:00PM', 'Friday', 3),
                (10129, 'PHYS 201', 'Fundamentals of Physics III', '03:00PM', '04:00PM', 'Tuesday', 3),

                # MATH 122 - Calculus II (1-hour lectures)
                (10130, 'MATH 122', 'Calculus II', '09:00AM', '10:00AM', 'Monday', 4),
                (10131, 'MATH 122', 'Calculus II', '11:00AM', '12:00PM', 'Wednesday', 4),
                (10132, 'MATH 122', 'Calculus II', '02:00PM', '03:00PM', 'Friday', 4),

                # MATH 123 - Calculus III (1-hour lectures)
                (10133, 'MATH 123', 'Calculus III', '08:00AM', '09:00AM', 'Tuesday', 4),
                (10134, 'MATH 123', 'Calculus III', '01:00PM', '02:00PM', 'Thursday', 4),
                (10135, 'MATH 123', 'Calculus III', '10:00AM', '11:00AM', 'Friday', 4),

                # MATH 200 - Multivariate Calculus (1-hour lectures)
                (10136, 'MATH 200', 'Multivariate Calculus', '10:00AM', '11:00AM', 'Tuesday', 4),
                (10137, 'MATH 200', 'Multivariate Calculus', '12:00PM', '01:00PM', 'Thursday', 4),
                (10138, 'MATH 200', 'Multivariate Calculus', '03:00PM', '04:00PM', 'Monday', 4),

                # MATH 201 - Linear Algebra (1-hour lectures)
                (10139, 'MATH 201', 'Linear Algebra', '09:00AM', '10:00AM', 'Wednesday', 4),
                (10140, 'MATH 201', 'Linear Algebra', '02:00PM', '03:00PM', 'Tuesday', 4),
                (10141, 'MATH 201', 'Linear Algebra', '11:00AM', '12:00PM', 'Friday', 4),

                # MATH 221 - Discrete Mathematics (1-hour lectures)
                (10142, 'MATH 221', 'Discrete Mathematics', '08:00AM', '09:00AM', 'Friday', 4),
                (10143, 'MATH 221', 'Discrete Mathematics', '01:00PM', '02:00PM', 'Wednesday', 4),
                (10144, 'MATH 221', 'Discrete Mathematics', '10:00AM', '11:00AM', 'Tuesday', 4),

                # MATH 311 - Probability and Statistics I (1-hour lectures)
                (10145, 'MATH 311', 'Probability and Statistics I', '10:00AM', '11:00AM', 'Monday', 4),
                (10146, 'MATH 311', 'Probability and Statistics I', '02:00PM', '03:00PM', 'Thursday', 4),
                (10147, 'MATH 311', 'Probability and Statistics I', '03:00PM', '04:00PM', 'Friday', 4),

                # CS 458 – Data Structures and Algorithms I
                (100148, 'CS 458', 'Data Structures and Algorithms I', '10:00AM', '11:30AM', 'Monday', 3),
                (100149, 'CS 458', 'Data Structures and Algorithms I', '01:00PM', '02:30PM', 'Wednesday', 3),
                (100150, 'CS 458', 'Data Structures and Algorithms I', '03:00PM', '04:30PM', 'Friday', 3),

                # CS 441 – Theory of Computation
                (100151, 'CS 441', 'Theory of Computation', '09:00AM', '10:30AM', 'Tuesday', 3),
                (100152, 'CS 441', 'Theory of Computation', '11:00AM', '12:30PM', 'Thursday', 3),
                (100153, 'CS 441', 'Theory of Computation', '02:00PM', '03:30PM', 'Monday', 3),

                # CS 429 – Operating Systems
                (100154, 'CS 429', 'Operating Systems', '08:30AM', '10:00AM', 'Wednesday', 3),
                (100155, 'CS 429', 'Operating Systems', '12:00PM', '01:30PM', 'Friday', 3),
                (100156, 'CS 429', 'Operating Systems', '03:30PM', '05:00PM', 'Tuesday', 3),

                # CS 461 – Database Systems
                (100157, 'CS 461', 'Database Systems', '09:00AM', '10:30AM', 'Monday', 3),
                (100158, 'CS 461', 'Database Systems', '01:00PM', '02:30PM', 'Thursday', 3),
                (100159, 'CS 461', 'Database Systems', '04:00PM', '05:30PM', 'Wednesday', 3),

                # CS 472 – Computer Networks
                (100160, 'CS 472', 'Computer Networks', '08:00AM', '09:30AM', 'Friday', 3),
                (100161, 'CS 472', 'Computer Networks', '10:00AM', '11:30AM', 'Tuesday', 3),
                (100162, 'CS 472', 'Computer Networks', '01:00PM', '02:30PM', 'Monday', 3),

                # CS 375 – Web Development
                (100163, 'CS 375', 'Web Development', '09:00AM', '10:30AM', 'Thursday', 3),
                (100164, 'CS 375', 'Web Development', '12:00PM', '01:30PM', 'Tuesday', 3),
                (100165, 'CS 375', 'Web Development', '03:00PM', '04:30PM', 'Friday', 3),

                # CS 380 – Artificial Intelligence
                (100166, 'CS 380', 'Artificial Intelligence', '10:00AM', '11:30AM', 'Wednesday', 3),
                (100167, 'CS 380', 'Artificial Intelligence', '01:00PM', '02:30PM', 'Friday', 3),
                (100168, 'CS 380', 'Artificial Intelligence', '03:30PM', '05:00PM', 'Monday', 3),

                # CS 475 – Network Security
                (100169, 'CS 475', 'Network Security', '08:00AM', '09:30AM', 'Thursday', 3),
                (100170, 'CS 475', 'Network Security', '11:00AM', '12:30PM', 'Tuesday', 3),
                (100171, 'CS 475', 'Network Security', '02:00PM', '03:30PM', 'Wednesday', 3),

                # CS 377 – Software Security
                (100172, 'CS 377', 'Software Security', '09:00AM', '10:30AM', 'Monday', 3),
                (100173, 'CS 377', 'Software Security', '12:00PM', '01:30PM', 'Thursday', 3),
                (100174, 'CS 377', 'Software Security', '03:00PM', '04:30PM', 'Tuesday', 3),

                # SE 320 – Software Testing
                (100175, 'SE 320', 'Software Testing', '09:00AM', '10:30AM', 'Tuesday', 3),
                (100176, 'SE 320', 'Software Testing', '11:00AM', '12:30PM', 'Thursday', 3),
                (100177, 'SE 320', 'Software Testing', '02:00PM', '03:30PM', 'Friday', 3)

            ]
        
            for course in mock_courses:
                if not Course.query.filter_by(crn=course[0]).first():
                    db.session.add(Course(crn=course[0], course_code=course[1], course_name=course[2],
                                         start_time=course[3], end_time=course[4], day=course[5], credits=course[6]))
                    inserted += 1
                    logger.debug(f"Inserted course: {course[1]} (CRN: {course[0]})")
            db.session.commit()
        logger.info(f"Database initialized with {inserted} new courses")
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)