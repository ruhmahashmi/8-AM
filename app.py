from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# Create a function to initialize the database
def init_db():
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

init_db()  # Initialize the database

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

    # Save to database
    conn = sqlite3.connect('schedule.db')
    c = conn.cursor()
    c.execute("INSERT INTO schedule (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
              (course1, course2, course3, course4, course5, course6, start_time, end_time, spacing))
    conn.commit()
    conn.close()

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

