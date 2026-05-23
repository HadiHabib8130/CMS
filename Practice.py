from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import sqlite3
import secrets
import string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "cms_fyp_secret_key_123"

DATABASE = os.path.join(os.path.dirname(__file__), "cms_db.sqlite")

# Connect to SQLite and initialize schema
db = sqlite3.connect(DATABASE, check_same_thread=False)
db.row_factory = sqlite3.Row
cursor = db.cursor()
# Enable foreign key support for cascading cleanup if needed
cursor.execute('PRAGMA foreign_keys = ON')

def add_column_if_missing(table, column_name, column_definition):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_definition}")


def table_exists(name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def init_db():
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
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
        )
        """
    )
    cursor.execute(
        """
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
        )
        """
    )
    if table_exists('subjects') and not table_exists('courses'):
        cursor.execute("ALTER TABLE subjects RENAME TO courses")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            credit_hours INTEGER,
            theory_hours INTEGER,
            practical_hours INTEGER,
            department TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            semester TEXT,
            year INTEGER,
            department TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS class_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            course_id INTEGER,
            teacher_id INTEGER,
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(course_id) REFERENCES courses(id),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        )
        """
    )
    cursor.execute(
        """
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
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            semester TEXT,
            amount_due REAL,
            amount_paid REAL,
            due_date TEXT,
            status TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """
    )
    db.commit()

    add_column_if_missing("students", "reg_id", "reg_id TEXT")
    add_column_if_missing("teachers", "reg_id", "reg_id TEXT")
    add_column_if_missing("teachers", "email", "email TEXT")
    add_column_if_missing("teachers", "phone", "phone TEXT")
    add_column_if_missing("teachers", "qualification", "qualification TEXT")
    add_column_if_missing("teachers", "specialization", "specialization TEXT")
    add_column_if_missing("courses", "code", "code TEXT UNIQUE")
    add_column_if_missing("courses", "credit_hours", "credit_hours INTEGER")
    add_column_if_missing("courses", "theory_hours", "theory_hours INTEGER")
    add_column_if_missing("courses", "practical_hours", "practical_hours INTEGER")
    add_column_if_missing("courses", "department", "department TEXT")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_reg_id ON students(reg_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_teachers_reg_id ON teachers(reg_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_code ON courses(code)")
    db.commit()

    cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] == 0:
        default_admin_password = generate_password_hash("Admin@123")
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", default_admin_password, "admin")
        )
        db.commit()


def generate_temp_password(length=10):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_reg_id(role):
    year = datetime.now().year
    if role == 'student':
        cursor.execute("SELECT COUNT(*) FROM students")
        count = cursor.fetchone()[0] or 0
        return f"STU{year}{count + 1:03d}"
    if role == 'teacher':
        cursor.execute("SELECT COUNT(*) FROM teachers")
        count = cursor.fetchone()[0] or 0
        return f"TEA{year}{count + 1:03d}"
    return None


def generate_username(role, reg_id):
    return reg_id.lower()


def split_degree(degree_text):
    if not degree_text:
        return '', ''
    parts = degree_text.split(' ', 1)
    if parts[0] in ('BS', 'MS', 'PhD'):
        return parts[0], parts[1] if len(parts) > 1 else ''
    return '', degree_text


init_db()

# Home route redirects to login
@app.route('/')
def home():
    return redirect(url_for('login'))

# Signup route is disabled for public access; admin creates accounts
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    flash("Account creation is admin-only. Please ask your administrator.", "warning")
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        account = cursor.fetchone()

        if account and check_password_hash(account['password'], password):
            session['username'] = account['username']
            session['role'] = account['role']

            # Redirect to the correct dashboard based on role
            if account['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif account['role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif account['role'] == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid username or password!", "danger")
            return redirect(url_for('login'))

    return render_template('Login.html')

# Admin Dashboard
@app.route('/admin')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        return render_template('admin.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# ---------------- Student Management CRUD ----------------

# View all students
@app.route('/admin/students')
def view_students():
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM students WHERE name LIKE ? OR reg_id LIKE ? OR degree LIKE ? OR program LIKE ? OR department LIKE ?",
                (pattern, pattern, pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()
        return render_template('admin_students.html', students=students)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Add new student
@app.route('/admin/students/add', methods=['GET', 'POST'])
def add_student():
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            degree_level = request.form['degree_level']
            degree_type = request.form['degree_type']
            degree = f"{degree_level} {degree_type}".strip()
            program = request.form['program']
            department = request.form['department']
            fee_status = request.form['fee_status']
            father_name = request.form['father_name']

            reg_id = generate_reg_id('student')
            username = generate_username('student', reg_id)
            temp_password = generate_temp_password()
            hashed_password = generate_password_hash(temp_password)

            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed_password, 'student')
            )
            user_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO students (user_id, reg_id, name, degree, program, department, fee_status, father_name) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, reg_id, name, degree, program, department, fee_status, father_name)
            )
            db.commit()
            flash(f"Student created with Reg ID {reg_id}, username {username}, temporary password {temp_password}", "success")
            return redirect(url_for('view_students'))
        return render_template('admin_add_student.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Edit student
@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM students WHERE id=?", (id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found!", "danger")
            return redirect(url_for('view_students'))

        if request.method == 'POST':
            name = request.form['name']
            degree_level = request.form['degree_level']
            degree_type = request.form['degree_type']
            degree = f"{degree_level} {degree_type}".strip()
            program = request.form['program']
            department = request.form['department']
            fee_status = request.form['fee_status']
            father_name = request.form['father_name']
            new_password = request.form.get('new_password', '').strip()

            cursor.execute(
                "UPDATE students SET name=?, degree=?, program=?, department=?, fee_status=?, father_name=? WHERE id=?",
                (name, degree, program, department, fee_status, father_name, id)
            )
            if new_password and student['user_id']:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password=? WHERE id=?", (hashed_password, student['user_id']))
            db.commit()
            flash("Student updated successfully!" + (" Password changed." if new_password else ""), "success")
            return redirect(url_for('view_students'))

        degree_level, degree_type = split_degree(student['degree'])
        return render_template('admin_edit_student.html', student=student, degree_level=degree_level, degree_type=degree_type)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Delete student
@app.route('/admin/students/delete/<int:id>', methods=['POST'])
def delete_student(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT user_id FROM students WHERE id=?", (id,))
        student = cursor.fetchone()
        if student:
            user_id = student['user_id']
            cursor.execute("DELETE FROM students WHERE id=?", (id,))
            if user_id:
                cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.commit()
            flash("Student deleted successfully!", "success")
        else:
            flash("Student not found!", "danger")
        return redirect(url_for('view_students'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Teacher management
@app.route('/admin/teachers')
def view_teachers():
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM teachers WHERE name LIKE ? OR reg_id LIKE ? OR email LIKE ? OR department LIKE ? OR title LIKE ? OR specialization LIKE ?",
                (pattern, pattern, pattern, pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT * FROM teachers")
        teachers = cursor.fetchall()
        return render_template('admin_teachers.html', teachers=teachers)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/teachers/add', methods=['GET', 'POST'])
def add_teacher():
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            qualification = request.form['qualification']
            selected_courses = request.form.getlist('specialization')
            specialization = ', '.join(selected_courses)
            department = request.form['department']
            title = request.form['title']

            reg_id = generate_reg_id('teacher')
            username = generate_username('teacher', reg_id)
            temp_password = generate_temp_password()
            hashed_password = generate_password_hash(temp_password)

            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed_password, 'teacher')
            )
            user_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO teachers (user_id, reg_id, name, email, phone, qualification, specialization, department, title) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, reg_id, name, email, phone, qualification, specialization, department, title)
            )
            db.commit()
            flash(f"Teacher created with Reg ID {reg_id}, username {username}, temporary password {temp_password}", "success")
            return redirect(url_for('view_teachers'))
        return render_template('admin_add_teacher.html', courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/teachers/edit/<int:id>', methods=['GET', 'POST'])
def edit_teacher(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM teachers WHERE id=?", (id,))
        teacher = cursor.fetchone()
        if not teacher:
            flash("Teacher not found!", "danger")
            return redirect(url_for('view_teachers'))

        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        selected_specializations = [item.strip() for item in (teacher['specialization'] or '').split(',') if item.strip()]

        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            qualification = request.form['qualification']
            selected_courses = request.form.getlist('specialization')
            specialization = ', '.join(selected_courses)
            department = request.form['department']
            title = request.form['title']

            cursor.execute(
                "UPDATE teachers SET name=?, email=?, phone=?, qualification=?, specialization=?, department=?, title=? WHERE id=?",
                (name, email, phone, qualification, specialization, department, title, id)
            )
            db.commit()
            flash("Teacher updated successfully.", "success")
            return redirect(url_for('view_teachers'))

        return render_template(
            'admin_edit_teacher.html',
            teacher=teacher,
            courses=courses,
            selected_specializations=selected_specializations
        )
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/teachers/delete/<int:id>', methods=['POST'])
def delete_teacher(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT user_id FROM teachers WHERE id=?", (id,))
        teacher = cursor.fetchone()
        if teacher:
            user_id = teacher['user_id']
            cursor.execute("DELETE FROM teachers WHERE id=?", (id,))
            if user_id:
                cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.commit()
            flash("Teacher deleted successfully!", "success")
        else:
            flash("Teacher not found!", "danger")
        return redirect(url_for('view_teachers'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses')
def view_courses():
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM courses WHERE name LIKE ? OR code LIKE ? OR department LIKE ?",
                (pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT * FROM courses")
        courses = cursor.fetchall()
        return render_template('admin_courses.html', courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/add', methods=['GET', 'POST'])
def add_course():
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            code = request.form['code']
            credit_hours = request.form.get('credit_hours') or None
            theory_hours = request.form.get('theory_hours') or None
            practical_hours = request.form.get('practical_hours') or None
            department = request.form['department']
            try:
                cursor.execute(
                    "INSERT INTO courses (name, code, credit_hours, theory_hours, practical_hours, department) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, code, credit_hours, theory_hours, practical_hours, department)
                )
                db.commit()
                flash(f"Course '{name}' added successfully.", "success")
                return redirect(url_for('view_courses'))
            except sqlite3.IntegrityError:
                flash("Course code must be unique.", "danger")
        return render_template('admin_add_course.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/edit/<int:id>', methods=['GET', 'POST'])
def edit_course(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM courses WHERE id=?", (id,))
        course = cursor.fetchone()
        if not course:
            flash("Course not found!", "danger")
            return redirect(url_for('view_courses'))
        if request.method == 'POST':
            name = request.form['name']
            code = request.form['code']
            credit_hours = request.form.get('credit_hours') or None
            theory_hours = request.form.get('theory_hours') or None
            practical_hours = request.form.get('practical_hours') or None
            department = request.form['department']
            try:
                cursor.execute(
                    "UPDATE courses SET name=?, code=?, credit_hours=?, theory_hours=?, practical_hours=?, department=? WHERE id=?",
                    (name, code, credit_hours, theory_hours, practical_hours, department, id)
                )
                db.commit()
                flash("Course updated successfully.", "success")
                return redirect(url_for('view_courses'))
            except sqlite3.IntegrityError:
                flash("Course code must be unique.", "danger")
        return render_template('admin_edit_course.html', course=course)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/delete/<int:id>', methods=['POST'])
def delete_course(id):
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("DELETE FROM courses WHERE id=?", (id,))
        db.commit()
        flash("Course deleted successfully!", "success")
        return redirect(url_for('view_courses'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


# Teacher Dashboard
@app.route('/teacher')
def teacher_dashboard():
    if 'role' in session and session['role'] == 'teacher':
        return render_template('Teacher.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Student Dashboard
@app.route('/student')
def student_dashboard():
    if 'role' in session and session['role'] == 'student':
        return render_template('Student.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
