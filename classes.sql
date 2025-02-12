-- No CREATE DATABASE statement in SQLite
-- Open or create the database directly using: sqlite3 classes.db

-- Remove SELECT classes; as it's not valid

CREATE TABLE course_requirements (
    course_code VARCHAR(10) PRIMARY KEY,
    course_name VARCHAR(100),
    credits REAL, -- Changed to REAL for SQLite compatibility
    alternative_course_code VARCHAR(10)
);

INSERT INTO course_requirements (course_code, course_name, credits, alternative_course_code) VALUES
('CS 164', 'Introduction to Computer Science', 3.0, NULL),
('CS 171', 'Computer Programming I', 3.0, 'CS 175'),
('CS 175', 'Advanced Computer Programming I', 3.0, 'CS 171'),
('CS 172', 'Computer Programming II', 3.0, NULL),
('CS 260', 'Data Structures', 4.0, NULL),
('CS 265', 'Advanced Programming Tools and Techniques', 3.0, NULL),
('CS 270', 'Mathematical Foundations of Computer Science', 3.0, NULL),
('CS 277', 'Algorithms and Analysis', 3.0, NULL),
('CS 281', 'Systems Architecture', 4.0, NULL),
('CS 283', 'Systems Programming', 3.0, NULL),
('CS 360', 'Programming Language Concepts', 3.0, NULL),
('SE 181', 'Introduction to Software Engineering and Development', 3.0, 'SE 201'),
('SE 201', 'Introduction to Software Engineering and Development', 3.0, 'SE 181'),
('SE 310', 'Software Architecture I', 3.0, NULL),
('CI 101', 'Computing and Informatics Design I', 2.0, NULL),
('CI 102', 'Computing and Informatics Design II', 2.0, NULL),
('CI 103', 'Computing and Informatics Design III', 2.0, NULL),
('CI 491', 'Senior Project I', 3.0, NULL),
('CI 492', 'Senior Project II', 3.0, NULL),
('CI 493', 'Senior Project III', 3.0, NULL),
('MATH 121', 'Calculus I', 4.0, NULL),
('MATH 122', 'Calculus II', 4.0, NULL),
('MATH 123', 'Calculus III', 4.0, NULL),
('MATH 200', 'Multivariate Calculus', 4.0, NULL),
('MATH 201', 'Linear Algebra', 4.0, NULL),
('MATH 221', 'Discrete Mathematics', 3.0, NULL),
('MATH 311', 'Probability and Statistics I', 4.0, NULL),
('BIO 131', 'Cells and Biomolecules', 3.0, NULL),
('BIO 134', 'Cells and Biomolecules Lab', 1.0, NULL),
('BIO 132', 'Genetics and Evolution', 3.0, NULL),
('BIO 135', 'Genetics and Evolution Lab', 1.0, NULL),
('BIO 133', 'Physiology and Ecology', 3.0, NULL),
('BIO 136', 'Anatomy and Ecology Lab', 1.0, NULL),
('CHEM 101', 'General Chemistry I', 4.0, NULL),
('CHEM 102', 'General Chemistry II', 4.0, NULL),
('CHEM 103', 'General Chemistry III', 4.0, NULL),
('PHYS 101', 'Fundamentals of Physics I', 4.0, NULL),
('PHYS 102', 'Fundamentals of Physics II', 4.0, NULL),
('PHYS 201', 'Fundamentals of Physics III', 4.0, NULL),
('COM 230', 'Techniques of Speaking', 3.0, NULL),
('ENGL 101', 'Composition and Rhetoric I: Inquiry and Exploratory Research', 3.0, 'ENGL 111'),
('ENGL 111', 'English Composition I', 3.0, 'ENGL 101'),
('ENGL 102', 'Composition and Rhetoric II: Advanced Research and Evidence-Based Writing', 3.0, 'ENGL 112'),
('ENGL 112', 'English Composition II', 3.0, 'ENGL 102'),
('ENGL 103', 'Composition and Rhetoric III: Themes and Genres', 3.0, 'ENGL 113'),
('ENGL 113', 'English Composition III', 3.0, 'ENGL 103'),
('PHIL 311', 'Ethics and Information Technology', 3.0, NULL),
('UNIV CI101', 'The Drexel Experience', 2.0, 'CI 120'),
('CI 120', 'CCI Transfer Student Seminar', 2.0, 'UNIV CI101'),
('CIVC 101', 'Introduction to Civic Engagement', 1.0, NULL),
('COOP 101', 'Career Management and Professional Development', 1.0, NULL);

SELECT * FROM course_requirements;
