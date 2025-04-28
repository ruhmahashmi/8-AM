from app import app, db, Course
with app.app_context():
    new_courses = Course[
        Course(course_code="10079", course_name="CI 101", start_time="08:00AM", end_time="09:00AM", day="Monday"),
    ]
    db.session.add_all(new_courses)
    db.session.commit()
    print(f"Added {len(new_courses)} new courses")