-- SQLite schema for Campus Management System

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    roll_no TEXT UNIQUE,
    degree TEXT,
    program TEXT,
    department TEXT,
    fee_status TEXT,
    father_name TEXT,
    user_id INTEGER,
    class_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    qualification TEXT,
    specialization TEXT,
    department TEXT,
    title TEXT,
    user_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT UNIQUE,
    credit_hours INTEGER,
    theory_hours INTEGER,
    practical_hours INTEGER,
    department TEXT
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    semester TEXT,
    year INTEGER,
    department TEXT
);

CREATE TABLE IF NOT EXISTS class_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER,
    course_id INTEGER,
    teacher_id INTEGER,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(course_id) REFERENCES courses(id),
    FOREIGN KEY(teacher_id) REFERENCES teachers(id)
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    grade TEXT,
    marks_obtained REAL,
    total_marks REAL,
    term TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(course_id) REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    semester TEXT,
    amount_due REAL,
    amount_paid REAL,
    due_date TEXT,
    status TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);
