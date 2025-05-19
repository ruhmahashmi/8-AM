from app import app, db, Course
with app.app_context():
    new_courses = Course.query.filter(Course.course_code.in_(['MATH 122', 'MATH 123', 'MATH 200', 'MATH 201', 'MATH 221', 'MATH 311'])).all()
    for course in new_courses:
        print(f"CRN: {course.crn}, Code: {course.course_code}, Name: {course.course_name}, Time: {course.start_time}-{course.end_time}, Day: {course.day}, Credits: {course.credits}")

logger.debug(f"Filtered {len(filtered_courses)} courses within {start_time}-{end_time}")
logger.debug(f"Course options: {course_options.keys()}")