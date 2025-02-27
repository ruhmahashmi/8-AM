import sqlite3

try:
    # Connect to database
    conn = sqlite3.connect('profile_user.db')
    cursor = conn.cursor()

    # Create table (if not exists) - keeping column order consistent
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT UNIQUE NOT NULL PRIMARY KEY,
        firstName TEXT NOT NULL,
        lastName TEXT NOT NULL,
        password TEXT NOT NULL,
        major TEXT NOT NULL,
        minor TEXT NOT NULL,
        year TEXT NOT NULL,
        coOp TEXT NOT NULL
    )''')
    
    try:
        # Insert data - matching column order with table creation
        cursor.execute("INSERT INTO users (email, firstName, lastName, password, major, minor, year, coOp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                      ('john.doe@example.com', 'John', 'Doe', 'password', 'Computer Science', 'Mathematics', '2023', 'Yes'))
        print("Data inserted successfully")
    except sqlite3.IntegrityError:
        print("Data already exists")
    
    conn.commit()
    
    # Select and display data
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    print("Data from database:")
    for row in rows:
        print(f"First Name: {row[1]}, Email: {row[0]}, Last Name: {row[2]}, Password: {row[3]}, Major: {row[4]}, Minor: {row[5]}, Year: {row[6]}, Co-op: {row[7]}")

except sqlite3.Error as e:
    print(f"An error occurred: {e}")

finally:
    if conn:
        conn.close()
        print("Database connection closed")