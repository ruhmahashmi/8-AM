from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import timedelta

app = Flask(__name__)

# Initialize the schedule database
def init_schedule_db():
    conn = sqlite3.connect('schedule.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course1 TEXT,
                    course2 TEXT,
                    course3 TEXT,
                    course4 TEXT,
                    course5 TEXT,
                    course6 TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    spacing TEXT
                )''')
    conn.commit()
    conn.close()

# Initialize the filtered_courses database
def init_filtered_courses_db():
    conn = sqlite3.connect('filtered_courses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS filtered_courses (
                    crn INTEGER PRIMARY KEY,
                    course_code TEXT,
                    course_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    day TEXT
                )''')
    conn.commit()
    conn.close()

# Initialize the all_courses database with mock data
def init_all_courses_db():
    conn = sqlite3.connect('all_courses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
                    crn INTEGER PRIMARY KEY,
                    course_code TEXT UNIQUE,
                    course_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    day TEXT
                )''')
    # Insert mock data (only if the table is empty)
    c.execute("SELECT COUNT(*) FROM courses")
    if c.fetchone()[0] == 0:
        mock_courses = [
            (1001, "CS 164", "Introduction to Computer Science", "9:00AM", "10:00AM", "Monday"),
            (1002, "CS 171", "Computer Programming I", "10:00AM", "11:00AM", "Tuesday"),
            (1003, "MATH 121", "Calculus I", "11:00AM", "12:00PM", "Wednesday"),
            (1004, "PHYS 101", "Fundamentals of Physics I", "1:00PM", "2:00PM", "Thursday"),
        ]
        c.executemany("INSERT INTO courses (crn, course_code, course_name, start_time, end_time, day) VALUES (?, ?, ?, ?, ?, ?)", mock_courses)
    conn.commit()
    conn.close()

# Helper function to convert time strings (e.g., "9:00AM", "9am", "9:00 am") to minutes since midnight for comparison
def time_to_minutes(time_str):
    if not time_str:
        return None
    
    # Normalize the time string: remove spaces, ensure colon, and standardize case
    time_str = time_str.strip().lower().replace(" ", "").replace("am", "AM").replace("pm", "PM")
    
    # Handle formats like "9am", "9:00am", "9:00 AM", etc.
    if ':' not in time_str:
        # Add default minutes if only hour is provided (e.g., "9am" -> "9:00AM")
        if len(time_str) == 3:  # e.g., "9am"
            time_str = f"{time_str[0:1]}:00{time_str[1:]}"
        elif len(time_str) == 4:  # e.g., "10am"
            time_str = f"{time_str[0:2]}:00{time_str[2:]}"
    
    # Now parse the normalized time string
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
        raise ValueError(f"Invalid time format after normalization: {time_str}")
    
    return hour * 60 + minute

# Helper function to convert minutes back to time string (e.g., "9:00AM")
def minutes_to_time(minutes):
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    period = "AM" if hours < 12 else "PM"
    if hours == 0:
        hours = 12  # Midnight
    elif hours > 12:
        hours -= 12
    return f"{hours:02d}:{mins:02d}{period}"

# Initialize all databases
init_schedule_db()
init_filtered_courses_db()
init_all_courses_db()

@app.route('/')
def home():
    return render_template('schedule.html')

@app.route('/save_schedule', methods=['POST'])
def save_schedule():
    # Get form data
    course1 = request.form.get('course1')
    course2 = request.form.get('course2')
    course3 = request.form.get('course3')
    course4 = request.form.get('course4')
    course5 = request.form.get('course5')
    course6 = request.form.get('course6')
    start_time = request.form.get('startTime')
    end_time = request.form.get('endTime')
    spacing = request.form.get('spacing')

    # Save to schedule.db
    conn = sqlite3.connect('schedule.db')
    c = conn.cursor()
    c.execute("INSERT INTO schedule (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
              (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing))
    conn.commit()
    schedule_id = c.lastrowid  # Get the ID of the newly inserted row
    conn.close()

    # Filter selected courses into filtered_courses.db based on time
    selected_courses = [course1, course2, course3, course4, course5, course6]
    selected_courses = [course for course in selected_courses if course]  # Remove empty selections

    if selected_courses and start_time and end_time:
        # Convert user-provided times to minutes for comparison
        user_start_minutes = time_to_minutes(start_time)
        user_end_minutes = time_to_minutes(end_time)

        # Connect to all_courses.db and filtered_courses.db
        conn_all = sqlite3.connect('all_courses.db')
        conn_filtered = sqlite3.connect('filtered_courses.db')
        c_all = conn_all.cursor()
        c_filtered = conn_filtered.cursor()

        # Clear previous filtered courses (optional)
        c_filtered.execute("DELETE FROM filtered_courses")

        # Filter courses from all_courses.db based on course_code and time range
        placeholders = ','.join('?' * len(selected_courses))
        c_all.execute(f"SELECT crn, course_code, course_name, start_time, end_time, day FROM courses WHERE course_code IN ({placeholders})", selected_courses)
        all_course_data = c_all.fetchall()

        # Filter courses based on time range (course start time must be >= user start time and course end time <= user end time)
        filtered_courses = []
        for crn, course_code, course_name, course_start, course_end, day in all_course_data:
            course_start_minutes = time_to_minutes(course_start)
            course_end_minutes = time_to_minutes(course_end)
            if (course_start_minutes >= user_start_minutes and course_end_minutes <= user_end_minutes):
                filtered_courses.append((crn, course_code, course_name, course_start, course_end, day))

        # Insert into filtered_courses.db
        if filtered_courses:
            c_filtered.executemany("INSERT INTO filtered_courses (crn, course_code, course_name, start_time, end_time, day) VALUES (?, ?, ?, ?, ?, ?)", filtered_courses)

        conn_all.commit()
        conn_filtered.commit()
        conn_all.close()
        conn_filtered.close()

    # Redirect to generate the schedule
    return redirect(url_for('generate_schedule', schedule_id=schedule_id))

@app.route('/generate_schedule')
def generate_schedule():
    schedule_id = request.args.get('schedule_id')
    if not schedule_id:
        return "No schedule ID provided", 400

    # Fetch schedule details from schedule.db
    conn_schedule = sqlite3.connect('schedule.db')
    c_schedule = conn_schedule.cursor()
    c_schedule.execute("SELECT course1, course2, course3, course4, course5, course6, start_time, end_time, spacing FROM schedule WHERE id = ?", (schedule_id,))
    schedule_data = c_schedule.fetchone()
    if not schedule_data:
        conn_schedule.close()
        return "Schedule not found", 404

    course1, course2, course3, course4, course5, course6, start_time, end_time, spacing = schedule_data
    conn_schedule.close()

    # Collect selected courses (remove None/empty)
    selected_courses = [c for c in [course1, course2, course3, course4, course5, course6] if c]
    if not selected_courses:
        return "No courses selected", 400

    # Get filtered courses from filtered_courses.db
    conn_filtered = sqlite3.connect('filtered_courses.db')
    c_filtered = conn_filtered.cursor()
    placeholders = ','.join('?' * len(selected_courses))
    c_filtered.execute(f"SELECT crn, course_code, course_name, start_time, end_time, day FROM filtered_courses WHERE course_code IN ({placeholders})", selected_courses)
    courses = c_filtered.fetchall()
    conn_filtered.close()

    if not courses:
        return "No matching courses found", 404

    # Convert times to minutes for scheduling
    user_start_minutes = time_to_minutes(start_time)
    user_end_minutes = time_to_minutes(end_time)

    # Available days (assuming Monday to Friday for simplicity)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule = {day: [] for day in days}  # Dictionary to store scheduled courses per day

    # Sort courses by duration (shortest first) to optimize scheduling
    courses_with_duration = [
        (crn, code, name, start, end, day, time_to_minutes(end) - time_to_minutes(start))
        for crn, code, name, start, end, day in courses
    ]
    courses_with_duration.sort(key=lambda x: x[6])  # Sort by duration

    # Schedule courses based on spacing preference
    spacing_gap = 30 if spacing == "spaced-out" else 0  # 30 minutes gap for spaced-out, 0 for back-to-back

    for crn, code, name, start, end, day, _ in courses_with_duration:
        start_minutes = time_to_minutes(start)
        end_minutes = time_to_minutes(end)
        duration = end_minutes - start_minutes

        # Find the first available day and time slot within user time frame
        scheduled = False
        for d in days:
            day_slots = schedule[d]
            can_schedule = True
            current_time = user_start_minutes

            # Check if the course can fit in this day without overlapping
            for slot_start, slot_end in day_slots:
                slot_start_minutes = time_to_minutes(slot_start)
                slot_end_minutes = time_to_minutes(slot_end)
                if current_time + duration + (spacing_gap if day_slots else 0) <= slot_start_minutes:
                    current_time = slot_start_minutes + spacing_gap  # Add gap if spaced-out
                elif current_time < slot_end_minutes and current_time + duration > slot_start_minutes:
                    can_schedule = False
                    break
                else:
                    current_time = max(current_time, slot_end_minutes) + spacing_gap

            if can_schedule and current_time + duration <= user_end_minutes:
                # Schedule the course at the current time on this day
                new_start = minutes_to_time(current_time)
                new_end = minutes_to_time(current_time + duration)
                schedule[d].append((new_start, new_end))
                scheduled = True
                break

        if not scheduled:
            # If no day can accommodate the course, we could skip it or handle differently (e.g., return an error)
            continue

    # Create a final schedule structure (e.g., list of tuples: (day, course_code, start_time, end_time))
    final_schedule = []
    for day in days:
        for start, end in schedule[day]:
            for crn, code, name, _, _, d in courses:
                if d == day and time_to_minutes(start) == time_to_minutes(courses_with_duration[0][3]) and time_to_minutes(end) == time_to_minutes(courses_with_duration[0][4]):
                    final_schedule.append((day, code, start, end))
                    break

    # For now, print the schedule (you can render it in a template or store it in a new table)
    schedule_output = "Generated Schedule:\n"
    for day, course, start, end in final_schedule:
        schedule_output += f"{day}: {course} ({start} - {end})\n"

    return schedule_output

if __name__ == '__main__':
    app.run(debug=True)