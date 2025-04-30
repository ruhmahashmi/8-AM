from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        conn = db.engine.connect()
        conn.execute(text("ALTER TABLE schedule ADD COLUMN is_priority BOOLEAN DEFAULT 0"))
        print("Successfully added is_priority column to schedule table")
        result = conn.execute(text("PRAGMA table_info(schedule)")).fetchall()
        columns = [row[1] for row in result]
        if 'is_priority' in columns:
            print("Verified: is_priority column exists in schedule table")
        else:
            print("Error: is_priority column not found after alteration")
        conn.close()
    except Exception as e:
        print(f"Error adding is_priority column: {str(e)}")