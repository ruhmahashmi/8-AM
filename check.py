import sqlite3

conn = sqlite3.connect('schedule.db')
c = conn.cursor()

c.execute("SELECT * FROM schedule")
data = c.fetchall()

conn.close()

for row in data:
    print(row)  # This prints all saved schedules
