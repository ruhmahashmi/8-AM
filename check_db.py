from app import app, db, Course
with app.app_context():
    # Count total rows
    total_rows = Course.query.count()
    # Get unique courses
    courses = db.session.query(Course.course_code, Course.course_name, Course.credits)\
                       .group_by(Course.course_code)\
                       .order_by(Course.course_code).all()
    print(f"Total rows in Course table: {total_rows}")
    print(f"Total unique course_code values: {len(courses)}")
    for course in courses:
        print(f"Course: {course.course_code}, Name: {course.course_name}, Credits: {course.credits}")
    # Check for duplicates or errors
    duplicates = db.session.query(Course.course_code, db.func.count())\
                          .group_by(Course.course_code)\
                          .having(db.func.count() > 1).all()
    print("\nCourses with multiple entries:")
    for dup in duplicates:
        print(f"Course: {dup[0]}, Count: {dup[1]}")