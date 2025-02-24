from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = '579-605-787'  # Needed for session storage

# Database setup function
def init_db():
    conn = sqlite3.connect('schedules.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
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
        )
    ''')
    conn.commit()
    conn.close()

# Route to display schedule page
@app.route('/')
def schedule():
    message = session.pop('message', '')  # Retrieve and remove message from session
    return render_template('schedule.html', message=message)

# Route to handle form submission
@app.route('/save_schedule', methods=['POST'])
def save_schedule():
    course1 = request.form.get('course1')
    course2 = request.form.get('course2')
    course3 = request.form.get('course3')
    course4 = request.form.get('course4')
    course5 = request.form.get('course5')
    course6 = request.form.get('course6')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    spacing = request.form.get('spacing')

    # Debugging: Print received input
    print(f"Received Schedule: {course1}, {course2}, {course3}, {course4}, {course5}, {course6}")
    print(f"Start Time: {start_time}, End Time: {end_time}, Spacing: {spacing}")

    # Save to database
    conn = sqlite3.connect('schedules.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO schedules (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing))
    conn.commit()
    conn.close()

    # Store message in session
    session['message'] = "Schedule saved successfully!"

    # Redirect back to home
    return redirect(url_for('schedule'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
