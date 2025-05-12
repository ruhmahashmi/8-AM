from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Connect to SQLite database using SQLAlchemy
        conn = db.engine.connect()
        
        # executes an ALTER TABLE, Add is_favorite column to schedule table, default value of 0
        conn.execute(text("ALTER TABLE schedule ADD COLUMN is_favorite BOOLEAN DEFAULT 0"))
        
        print("Successfully added is_favorite column to schedule table")
        
        # Verify the column was added, checking the table's structure
        # successful logs a confirmation; if not logs an error with details
        result = conn.execute(text("PRAGMA table_info(schedule)")).fetchall()
        columns = [row[1] for row in result]
        if 'is_favorite' in columns:
            print("Verified: is_favorite column exists in schedule table")
        else:
            print("Error: is_favorite column not found after alteration")
        
        conn.close()
    except Exception as e:
        print(f"Error adding is_favorite column: {str(e)}")