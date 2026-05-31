from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import os
import psycopg2
from psycopg2.extras import DictCursor
import secrets
import string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cms_fyp_secret_key_123")

def get_db():
    if 'db' not in g:
        # Vercel provides POSTGRES_URL when you add the Postgres integration
        db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
        g.db = psycopg2.connect(db_url, cursor_factory=DictCursor)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def add_column_if_missing(cursor, table, column_name, column_definition):
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
        (table, column_name)
    )
    if not cursor.fetchone():
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_definition}")

def table_exists(cursor, name):
    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (name,))
    return cursor.fetchone()[0]

def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
    if table_exists(cursor, 'subjects') and not table_exists(cursor, 'courses'):
        cursor.execute("ALTER TABLE subjects RENAME TO courses")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id SERIAL PRIMARY KEY,
            class_id INTEGER,
            teacher_id INTEGER,
            title TEXT,
            description TEXT,
            due_date TEXT,
            created_at TEXT,
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS class_attendance (
            id SERIAL PRIMARY KEY,
            class_id INTEGER,
            student_id INTEGER,
            course_id INTEGER,
            date TEXT,
            status TEXT,
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_attendance (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER,
            date TEXT,
            status TEXT,
            notes TEXT,
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
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


def get_teacher_by_username(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT t.* FROM teachers t JOIN users u ON t.user_id=u.id WHERE u.username=%s",
        (username,)
    )
    return cursor.fetchone()


def get_student_by_username(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT s.* FROM students s JOIN users u ON s.user_id=u.id WHERE u.username=%s",
        (username,)
    )
    return cursor.fetchone()


def get_teacher_assignments(teacher_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT cs.*, cl.name AS class_name, cl.semester, cl.year, cl.department AS class_department,
               co.name AS course_name, co.code AS course_code
        FROM class_subjects cs
        JOIN classes cl ON cs.class_id = cl.id
        JOIN courses co ON cs.course_id = co.id
        WHERE cs.teacher_id = %s
        """,
        (teacher_id,)
    )
    return cursor.fetchall()


def get_student_courses(student_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT co.* FROM class_subjects cs
        JOIN courses co ON cs.course_id = co.id
        WHERE cs.class_id = (
            SELECT class_id FROM students WHERE id = %s
        )
        """,
        (student_id,)
    )
    return cursor.fetchall()

# Home route redirects to login
@app.route('/')
def home():
    with app.app_context():
        init_db()
    return redirect(url_for('login'))

# Signup route is disabled for public access; admin creates accounts
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    flash("Account creation is admin-only. Please ask your administrator.", "warning")
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
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

# Add new admin
@app.route('/admin/add_admin', methods=['GET', 'POST'])
def add_admin():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            if cursor.fetchone():
                flash("Username already exists!", "danger")
            else:
                hashed_password = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, hashed_password, 'admin')
                )
                db.commit()
                flash(f"Admin account '{username}' created successfully.", "success")
                return redirect(url_for('admin_dashboard'))
        return render_template('admin_add_admin.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# ---------------- Student Management CRUD ----------------

# View all students
@app.route('/admin/students')
def view_students():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT s.*, c.name AS class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id "
                "WHERE s.name LIKE %s OR s.reg_id LIKE %s OR s.degree LIKE %s OR s.program LIKE %s OR s.department LIKE %s OR c.name LIKE %s",
                (pattern, pattern, pattern, pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT s.*, c.name AS class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id")
        students = cursor.fetchall()
        return render_template('admin_students.html', students=students)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Add new student
@app.route('/admin/students/add', methods=['GET', 'POST'])
def add_student():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT id, name FROM classes ORDER BY name")
        classes = cursor.fetchall()
        if request.method == 'POST':
            name = request.form['name']
            degree_level = request.form['degree_level']
            degree_type = request.form['degree_type']
            degree = f"{degree_level} {degree_type}".strip()
            program = request.form['program']
            department = request.form['department']
            fee_status = request.form['fee_status']
            father_name = request.form['father_name']
            class_id = request.form.get('class_id') or None

            reg_id = generate_reg_id('student')
            username = generate_username('student', reg_id)
            temp_password = generate_temp_password()
            hashed_password = generate_password_hash(temp_password)

            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING id",
                (username, hashed_password, 'student')
            )
            user_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO students (user_id, reg_id, name, degree, program, department, fee_status, father_name, class_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, reg_id, name, degree, program, department, fee_status, father_name, class_id)
            )
            db.commit()
            flash(f"Student created with Reg ID {reg_id}, username {username}, temporary password {temp_password}", "success")
            return redirect(url_for('view_students'))
        return render_template('admin_add_student.html', classes=classes)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Edit student
@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found!", "danger")
            return redirect(url_for('view_students'))

        cursor.execute("SELECT id, name FROM classes ORDER BY name")
        classes = cursor.fetchall()

        if request.method == 'POST':
            name = request.form['name']
            degree_level = request.form['degree_level']
            degree_type = request.form['degree_type']
            degree = f"{degree_level} {degree_type}".strip()
            program = request.form['program']
            department = request.form['department']
            fee_status = request.form['fee_status']
            father_name = request.form['father_name']
            class_id = request.form.get('class_id') or None
            new_password = request.form.get('new_password', '').strip()

            cursor.execute(
                "UPDATE students SET name=%s, degree=%s, program=%s, department=%s, fee_status=%s, father_name=%s, class_id=%s WHERE id= %s",
                (name, degree, program, department, fee_status, father_name, class_id, id)
            )
            if new_password and student['user_id']:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, student['user_id']))
            db.commit()
            flash("Student updated successfully!" + (" Password changed." if new_password else ""), "success")
            return redirect(url_for('view_students'))

        degree_level, degree_type = split_degree(student['degree'])
        return render_template('admin_edit_student.html', student=student, degree_level=degree_level, degree_type=degree_type, classes=classes)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))

# Delete student
@app.route('/admin/students/delete/<int:id>', methods=['POST'])
def delete_student(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT user_id FROM students WHERE id=%s", (id,))
        student = cursor.fetchone()
        if student:
            user_id = student['user_id']
            cursor.execute("DELETE FROM students WHERE id=%s", (id,))
            if user_id:
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
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
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM teachers WHERE name LIKE %s OR reg_id LIKE %s OR email LIKE %s OR department LIKE %s OR title LIKE %s OR specialization LIKE %s",
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
    db = get_db()
    cursor = db.cursor()
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
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING id",
                (username, hashed_password, 'teacher')
            )
            user_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO teachers (user_id, reg_id, name, email, phone, qualification, specialization, department, title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM teachers WHERE id=%s", (id,))
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
            new_password = request.form.get('password')

            cursor.execute(
                "UPDATE teachers SET name=%s, email=%s, phone=%s, qualification=%s, specialization=%s, department=%s, title=%s WHERE id=%s",
                (name, email, phone, qualification, specialization, department, title, id)
            )

            if new_password:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, teacher['user_id']))

            db.commit()
            flash("Teacher updated successfully." + (" Password changed." if new_password else ""), "success")
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
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT user_id FROM teachers WHERE id=%s", (id,))
        teacher = cursor.fetchone()
        if teacher:
            user_id = teacher['user_id']
            cursor.execute("DELETE FROM teachers WHERE id=%s", (id,))
            if user_id:
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
            db.commit()
            flash("Teacher deleted successfully!", "success")
        else:
            flash("Teacher not found!", "danger")
        return redirect(url_for('view_teachers'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/classes')
def view_classes():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM classes WHERE name LIKE %s OR semester LIKE %s OR department LIKE %s",
                (pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT * FROM classes")
        classes = cursor.fetchall()
        return render_template('admin_classes.html', classes=classes)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/classes/add', methods=['GET', 'POST'])
def add_class():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        cursor.execute("SELECT id, name, reg_id, specialization FROM teachers ORDER BY name")
        teachers = cursor.fetchall()
        if request.method == 'POST':
            name = request.form['name']
            semester = request.form['semester']
            year = request.form['year']
            department = request.form['department']

            cursor.execute(
                "INSERT INTO classes (name, semester, year, department) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, semester, year, department)
            )
            class_id = cursor.fetchone()[0]

            selected_courses = request.form.getlist('course_ids')
            for course_id in selected_courses:
                cursor.execute("SELECT name FROM courses WHERE id=%s", (course_id,))
                course = cursor.fetchone()
                if not course:
                    continue
                teacher_id = request.form.get(f'teacher_for_{course_id}') or None
                if not teacher_id:
                    flash(f"Please assign a teacher for {course['name']}", "danger")
                    return render_template('admin_add_class.html', courses=courses, teachers=teachers)
                cursor.execute("SELECT specialization FROM teachers WHERE id=%s", (teacher_id,))
                teacher = cursor.fetchone()
                allowed = [item.strip() for item in (teacher['specialization'] or '').split(',') if item.strip()]
                if course['name'] not in allowed:
                    flash(f"Teacher must specialize in {course['name']} to be assigned.", "danger")
                    return render_template('admin_add_class.html', courses=courses, teachers=teachers)
                cursor.execute(
                    "INSERT INTO class_subjects (class_id, course_id, teacher_id) VALUES (%s, %s, %s)",
                    (class_id, course_id, teacher_id)
                )
            db.commit()
            flash("Class created successfully.", "success")
            return redirect(url_for('view_classes'))
        return render_template('admin_add_class.html', courses=courses, teachers=teachers)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/classes/edit/<int:id>', methods=['GET', 'POST'])
def edit_class(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM classes WHERE id=%s", (id,))
        class_row = cursor.fetchone()
        if not class_row:
            flash("Class not found!", "danger")
            return redirect(url_for('view_classes'))

        if request.method == 'POST':
            name = request.form['name']
            semester = request.form['semester']
            year = request.form['year']
            department = request.form['department']

            cursor.execute(
                "UPDATE classes SET name=%s, semester=%s, year=%s, department=%s WHERE id=%s",
                (name, semester, year, department, id)
            )
            cursor.execute("DELETE FROM class_subjects WHERE class_id=%s", (id,))
            selected_courses = request.form.getlist('course_ids')
            for course_id in selected_courses:
                cursor.execute("SELECT name FROM courses WHERE id=%s", (course_id,))
                course = cursor.fetchone()
                if not course:
                    continue
                teacher_id = request.form.get(f'teacher_for_{course_id}') or None
                if not teacher_id:
                    flash(f"Please assign a teacher for {course['name']}", "danger")
                    # Refresh data before rendering
                    cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
                    courses = cursor.fetchall()
                    cursor.execute("SELECT id, name, reg_id, specialization FROM teachers ORDER BY name")
                    teachers = cursor.fetchall()
                    cursor.execute("SELECT course_id, teacher_id FROM class_subjects WHERE class_id=%s", (id,))
                    assigned = {row['course_id']: row['teacher_id'] for row in cursor.fetchall()}
                    return render_template('admin_edit_class.html', class_row=class_row, courses=courses, teachers=teachers, assigned=assigned)
                
                cursor.execute("SELECT specialization FROM teachers WHERE id=%s", (teacher_id,))
                teacher = cursor.fetchone()
                allowed = [item.strip() for item in (teacher['specialization'] or '').split(',') if item.strip()]
                if course['name'] not in allowed:
                    flash(f"Teacher must specialize in {course['name']} to be assigned.", "danger")
                    # Refresh data before rendering
                    cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
                    courses = cursor.fetchall()
                    cursor.execute("SELECT id, name, reg_id, specialization FROM teachers ORDER BY name")
                    teachers = cursor.fetchall()
                    cursor.execute("SELECT course_id, teacher_id FROM class_subjects WHERE class_id=%s", (id,))
                    assigned = {row['course_id']: row['teacher_id'] for row in cursor.fetchall()}
                    return render_template('admin_edit_class.html', class_row=class_row, courses=courses, teachers=teachers, assigned=assigned)
                cursor.execute(
                    "INSERT INTO class_subjects (class_id, course_id, teacher_id) VALUES (%s, %s, %s)",
                    (id, course_id, teacher_id)
                )
            db.commit()
            flash("Class updated successfully.", "success")
            return redirect(url_for('view_classes'))

        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        cursor.execute("SELECT id, name, reg_id, specialization FROM teachers ORDER BY name")
        teachers = cursor.fetchall()
        cursor.execute("SELECT course_id, teacher_id FROM class_subjects WHERE class_id=%s", (id,))
        assigned = {row['course_id']: row['teacher_id'] for row in cursor.fetchall()}
        return render_template('admin_edit_class.html', class_row=class_row, courses=courses, teachers=teachers, assigned=assigned)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/classes/delete/<int:id>', methods=['POST'])
def delete_class(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("DELETE FROM class_subjects WHERE class_id=%s", (id,))
        cursor.execute("DELETE FROM classes WHERE id=%s", (id,))
        db.commit()
        flash("Class deleted successfully!", "success")
        return redirect(url_for('view_classes'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/fees')
def view_fees():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute(
            "SELECT f.*, s.name AS student_name, s.reg_id FROM fees f JOIN students s ON f.student_id = s.id"
        )
        fees = cursor.fetchall()
        return render_template('admin_fees.html', fees=fees)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/fees/add', methods=['GET', 'POST'])
def add_fee():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT id, name, reg_id FROM students ORDER BY name")
        students = cursor.fetchall()
        if request.method == 'POST':
            student_id = request.form['student_id']
            semester = request.form['semester']
            amount_due = request.form['amount_due']
            amount_paid = request.form['amount_paid']
            due_date = request.form['due_date']
            status = request.form['status']
            cursor.execute(
                "INSERT INTO fees (student_id, semester, amount_due, amount_paid, due_date, status) VALUES (%s, %s, %s, %s, %s, %s)",
                (student_id, semester, amount_due, amount_paid, due_date, status)
            )
            db.commit()
            flash("Fee record added successfully.", "success")
            return redirect(url_for('view_fees'))
        return render_template('admin_add_fee.html', students=students)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/fees/edit/<int:id>', methods=['GET', 'POST'])
def edit_fee(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM fees WHERE id=%s", (id,))
        fee = cursor.fetchone()
        if not fee:
            flash("Fee record not found!", "danger")
            return redirect(url_for('view_fees'))
        cursor.execute("SELECT id, name, reg_id FROM students ORDER BY name")
        students = cursor.fetchall()
        if request.method == 'POST':
            student_id = request.form['student_id']
            semester = request.form['semester']
            amount_due = request.form['amount_due']
            amount_paid = request.form['amount_paid']
            due_date = request.form['due_date']
            status = request.form['status']
            cursor.execute(
                "UPDATE fees SET student_id=%s, semester=%s, amount_due=%s, amount_paid=%s, due_date=%s, status=%s WHERE id=%s",
                (student_id, semester, amount_due, amount_paid, due_date, status, id)
            )
            db.commit()
            flash("Fee record updated successfully.", "success")
            return redirect(url_for('view_fees'))
        return render_template('admin_edit_fee.html', fee=fee, students=students)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/fees/delete/<int:id>', methods=['POST'])
def delete_fee(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("DELETE FROM fees WHERE id=%s", (id,))
        db.commit()
        flash("Fee record deleted successfully!", "success")
        return redirect(url_for('view_fees'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/results')
def view_results():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute(
            """
            SELECT r.*, s.name AS student_name, s.reg_id, co.name AS course_name, co.code AS course_code
            FROM results r
            JOIN students s ON r.student_id = s.id
            JOIN courses co ON r.course_id = co.id
            """
        )
        results = cursor.fetchall()
        return render_template('admin_results.html', results=results)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/teacher-attendance', methods=['GET', 'POST'])
def admin_teacher_attendance():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            teacher_id = request.form['teacher_id']
            date = request.form['date']
            status = request.form['status']
            notes = request.form['notes']
            cursor.execute(
                "INSERT INTO teacher_attendance (teacher_id, date, status, notes) VALUES (%s, %s, %s, %s)",
                (teacher_id, date, status, notes)
            )
            db.commit()
            flash("Teacher attendance recorded successfully.", "success")
            return redirect(url_for('admin_teacher_attendance'))

        cursor.execute("SELECT id, name, reg_id FROM teachers ORDER BY name")
        teachers = cursor.fetchall()
        cursor.execute(
            "SELECT ta.*, t.name AS teacher_name, t.reg_id FROM teacher_attendance ta JOIN teachers t ON ta.teacher_id=t.id ORDER BY ta.date DESC"
        )
        records = cursor.fetchall()
        return render_template('admin_teacher_attendance.html', teachers=teachers, records=records)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/results/add', methods=['GET', 'POST'])
def add_result():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT id, name, reg_id FROM students ORDER BY name")
        students = cursor.fetchall()
        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        if request.method == 'POST':
            student_id = request.form['student_id']
            course_id = request.form['course_id']
            grade = request.form['grade']
            marks_obtained = request.form['marks_obtained']
            total_marks = request.form['total_marks']
            term = request.form['term']
            cursor.execute(
                "INSERT INTO results (student_id, course_id, grade, marks_obtained, total_marks, term) VALUES (%s, %s, %s, %s, %s, %s)",
                (student_id, course_id, grade, marks_obtained, total_marks, term)
            )
            db.commit()
            flash("Result added successfully.", "success")
            return redirect(url_for('view_results'))
        return render_template('admin_add_result.html', students=students, courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/results/edit/<int:id>', methods=['GET', 'POST'])
def edit_result(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM results WHERE id=%s", (id,))
        result = cursor.fetchone()
        if not result:
            flash("Result not found!", "danger")
            return redirect(url_for('view_results'))
        cursor.execute("SELECT id, name, reg_id FROM students ORDER BY name")
        students = cursor.fetchall()
        cursor.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cursor.fetchall()
        if request.method == 'POST':
            student_id = request.form['student_id']
            course_id = request.form['course_id']
            grade = request.form['grade']
            marks_obtained = request.form['marks_obtained']
            total_marks = request.form['total_marks']
            term = request.form['term']
            cursor.execute(
                "UPDATE results SET student_id=%s, course_id=%s, grade=%s, marks_obtained=%s, total_marks=%s, term=%s WHERE id=%s",
                (student_id, course_id, grade, marks_obtained, total_marks, term, id)
            )
            db.commit()
            flash("Result updated successfully.", "success")
            return redirect(url_for('view_results'))
        return render_template('admin_edit_result.html', result=result, students=students, courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/results/delete/<int:id>', methods=['POST'])
def delete_result(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("DELETE FROM results WHERE id=%s", (id,))
        db.commit()
        flash("Result deleted successfully!", "success")
        return redirect(url_for('view_results'))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses')
def view_courses():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        search = request.args.get('q', '').strip()
        if search:
            pattern = f"%{search}%"
            cursor.execute(
                "SELECT * FROM courses WHERE name LIKE %s OR code LIKE %s OR department LIKE %s",
                (pattern, pattern, pattern)
            )
        else:
            cursor.execute("SELECT * FROM courses")
        courses = cursor.fetchall()
        return render_template('admin_courses.html', courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher')
def teacher_dashboard():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))

        assignments = get_teacher_assignments(teacher['id'])
        classes = {}
        course_codes = set()
        class_ids = set()
        for row in assignments:
            class_ids.add(row['class_id'])
            course_codes.add(row['course_code'])
            classes.setdefault(row['class_id'], {
                'name': row['class_name'],
                'semester': row['semester'],
                'year': row['year'],
                'department': row['class_department'],
                'courses': []
            })
            classes[row['class_id']]['courses'].append({
                'course_name': row['course_name'],
                'course_code': row['course_code']
            })

        student_count = 0
        if class_ids:
            cursor.execute(
                "SELECT COUNT(DISTINCT id) FROM students WHERE class_id IN ({seq})".format(seq=','.join('?'*len(class_ids))),
                tuple(class_ids)
            )
            student_count = cursor.fetchone()[0]

        return render_template(
            'Teacher.html',
            teacher=teacher,
            assignments=classes.values(),
            class_count=len(classes),
            course_count=len(course_codes),
            student_count=student_count
        )
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/classes')
def teacher_classes():
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        assignments = get_teacher_assignments(teacher['id'])
        return render_template('teacher_classes.html', teacher=teacher, assignments=assignments)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/class/<int:id>/students')
def teacher_class_students(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        cursor.execute("SELECT * FROM class_subjects WHERE class_id=%s AND teacher_id=%s", (id, teacher['id']))
        assignment = cursor.fetchone()
        if not assignment:
            flash("You are not assigned to this class.", "danger")
            return redirect(url_for('teacher_classes'))
        cursor.execute("SELECT * FROM students WHERE class_id=%s", (id,))
        students = cursor.fetchall()
        cursor.execute(
            "SELECT co.id, co.name, co.code FROM class_subjects cs JOIN courses co ON cs.course_id=co.id WHERE cs.class_id=%s AND cs.teacher_id=%s",
            (id, teacher['id'])
        )
        courses = cursor.fetchall()
        return render_template('teacher_class_students.html', students=students, courses=courses, class_id=id)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/class/<int:id>/assignments', methods=['GET', 'POST'])
def teacher_class_assignments(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        cursor.execute("SELECT * FROM class_subjects WHERE class_id=%s AND teacher_id=%s", (id, teacher['id']))
        assignment = cursor.fetchone()
        if not assignment:
            flash("You are not assigned to this class.", "danger")
            return redirect(url_for('teacher_classes'))
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            due_date = request.form['due_date']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO assignments (class_id, teacher_id, title, description, due_date, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (id, teacher['id'], title, description, due_date, created_at)
            )
            db.commit()
            flash("Assignment created successfully.", "success")
            return redirect(url_for('teacher_class_assignments', id=id))
        cursor.execute("SELECT * FROM assignments WHERE class_id=%s AND teacher_id=%s ORDER BY due_date DESC", (id, teacher['id']))
        assignments = cursor.fetchall()
        return render_template('teacher_class_assignments.html', class_id=id, assignments=assignments)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/class/<int:class_id>/assignments/edit/<int:assignment_id>', methods=['GET', 'POST'])
def edit_assignment(class_id, assignment_id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        cursor.execute("SELECT * FROM class_subjects WHERE class_id=%s AND teacher_id=%s", (class_id, teacher['id']))
        if not cursor.fetchone():
            flash("You are not assigned to this class.", "danger")
            return redirect(url_for('teacher_classes'))
        
        cursor.execute("SELECT * FROM assignments WHERE id=%s AND class_id=%s AND teacher_id=%s", (assignment_id, class_id, teacher['id']))
        assignment = cursor.fetchone()
        if not assignment:
            flash("Assignment not found.", "danger")
            return redirect(url_for('teacher_class_assignments', id=class_id))
            
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            due_date = request.form['due_date']
            
            cursor.execute(
                "UPDATE assignments SET title=%s, description=%s, due_date=%s WHERE id=%s",
                (title, description, due_date, assignment_id)
            )
            db.commit()
            flash("Assignment updated successfully.", "success")
            return redirect(url_for('teacher_class_assignments', id=class_id))
            
        return render_template('teacher_edit_assignment.html', class_id=class_id, assignment=assignment)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/class/<int:class_id>/assignments/delete/<int:assignment_id>', methods=['POST'])
def delete_assignment(class_id, assignment_id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        cursor.execute("SELECT * FROM class_subjects WHERE class_id=%s AND teacher_id=%s", (class_id, teacher['id']))
        if not cursor.fetchone():
            flash("You are not assigned to this class.", "danger")
            return redirect(url_for('teacher_classes'))
            
        cursor.execute("DELETE FROM assignments WHERE id=%s AND class_id=%s AND teacher_id=%s", (assignment_id, class_id, teacher['id']))
        db.commit()
        flash("Assignment deleted successfully.", "success")
        return redirect(url_for('teacher_class_assignments', id=class_id))
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/class/<int:id>/attendance', methods=['GET', 'POST'])
def teacher_class_attendance(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        cursor.execute("SELECT * FROM class_subjects WHERE class_id=%s AND teacher_id=%s", (id, teacher['id']))
        assignment = cursor.fetchone()
        if not assignment:
            flash("You are not assigned to this class.", "danger")
            return redirect(url_for('teacher_classes'))
        cursor.execute("SELECT * FROM students WHERE class_id=%s", (id,))
        students = cursor.fetchall()
        cursor.execute(
            "SELECT co.id, co.name, co.code FROM class_subjects cs JOIN courses co ON cs.course_id=co.id WHERE cs.class_id=%s AND cs.teacher_id=%s",
            (id, teacher['id'])
        )
        courses = cursor.fetchall()
        if request.method == 'POST':
            date = request.form['date']
            course_id = request.form['course_id']
            present_ids = request.form.getlist('present_student')
            for student in students:
                status = 'Present' if str(student['id']) in present_ids else 'Absent'
                cursor.execute(
                    "INSERT INTO class_attendance (class_id, student_id, course_id, date, status) VALUES (%s, %s, %s, %s, %s)",
                    (id, student['id'], course_id, date, status)
                )
            db.commit()
            flash("Attendance recorded successfully.", "success")
            return redirect(url_for('teacher_class_attendance', id=id))
        return render_template('teacher_class_attendance.html', students=students, courses=courses, class_id=id)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/results', methods=['GET', 'POST'])
def teacher_results():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))

        assignments = get_teacher_assignments(teacher['id'])
        class_ids = [row['class_id'] for row in assignments]
        if class_ids:
            cursor.execute(
                "SELECT * FROM students WHERE class_id IN ({seq})".format(seq=','.join('?'*len(class_ids))),
                tuple(class_ids)
            )
            students = cursor.fetchall()
        else:
            students = []

        course_ids = [row['course_id'] for row in assignments]
        if course_ids:
            cursor.execute(
                "SELECT * FROM courses WHERE id IN ({seq})".format(seq=','.join('?'*len(course_ids))),
                tuple(course_ids)
            )
            courses = cursor.fetchall()
        else:
            courses = []

        student_ids = [s['id'] for s in students]
        if student_ids:
            cursor.execute(
                """
                SELECT r.*, s.name AS student_name, co.name AS course_name, co.code AS course_code
                FROM results r
                JOIN students s ON r.student_id = s.id
                JOIN courses co ON r.course_id = co.id
                WHERE r.student_id IN ({seq})
                """.format(seq=','.join('?'*len(student_ids))),
                tuple(student_ids)
            )
            teacher_results = cursor.fetchall()
        else:
            teacher_results = []

        if request.method == 'POST':
            student_id = request.form['student_id']
            course_id = request.form['course_id']
            grade = request.form['grade']
            marks_obtained = request.form['marks_obtained']
            total_marks = request.form['total_marks']
            term = request.form['term']
            cursor.execute(
                "INSERT INTO results (student_id, course_id, grade, marks_obtained, total_marks, term) VALUES (%s, %s, %s, %s, %s, %s)",
                (student_id, course_id, grade, marks_obtained, total_marks, term)
            )
            db.commit()
            flash("Result added successfully.", "success")
            return redirect(url_for('teacher_results'))

        return render_template('teacher_results.html', teacher=teacher, students=students, courses=courses, results=teacher_results)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/my-attendance')
def teacher_my_attendance():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        if not teacher:
            flash("Teacher profile not found.", "danger")
            return redirect(url_for('logout'))
        
        cursor.execute(
            "SELECT * FROM teacher_attendance WHERE teacher_id = %s ORDER BY date DESC",
            (teacher['id'],)
        )
        records = cursor.fetchall()
        return render_template('teacher_my_attendance.html', teacher=teacher, records=records)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/teacher/feedback')
def teacher_feedback():
    if 'role' in session and session['role'] == 'teacher':
        teacher = get_teacher_by_username(session['username'])
        return render_template('teacher_feedback.html', teacher=teacher)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student')
def student_dashboard():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        if not student:
            flash("Student profile not found.", "danger")
            return redirect(url_for('logout'))
        courses = get_student_courses(student['id'])
        cursor.execute("SELECT * FROM results WHERE student_id=%s", (student['id'],))
        results = cursor.fetchall()
        cursor.execute("SELECT * FROM fees WHERE student_id=%s", (student['id'],))
        fees = cursor.fetchall()

        due_amount = sum((fee['amount_due'] or 0) - (fee['amount_paid'] or 0) for fee in fees if fee['status'] != 'Paid')
        paid_amount = sum((fee['amount_paid'] or 0) for fee in fees)
        pending_fees = len([fee for fee in fees if fee['status'] != 'Paid'])

        return render_template(
            'Student.html',
            student=student,
            courses=courses,
            results=results,
            fees=fees,
            total_courses=len(courses),
            total_results=len(results),
            total_fees=len(fees),
            due_amount=due_amount,
            paid_amount=paid_amount,
            pending_fees=pending_fees
        )
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/profile')
def student_profile():
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        return render_template('student_profile.html', student=student)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/courses')
def student_courses():
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        courses = get_student_courses(student['id'])
        return render_template('student_courses.html', student=student, courses=courses)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/results')
def student_results():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        cursor.execute(
            "SELECT r.*, co.name AS course_name, co.code AS course_code FROM results r JOIN courses co ON r.course_id=co.id WHERE r.student_id=%s",
            (student['id'],)
        )
        results = cursor.fetchall()
        return render_template('student_results.html', student=student, results=results)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/course/<int:course_id>/attendance')
def student_course_attendance(course_id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        if not student:
            flash("Student profile not found.", "danger")
            return redirect(url_for('logout'))
        
        cursor.execute(
            """
            SELECT ca.*, co.name AS course_name, co.code AS course_code 
            FROM class_attendance ca 
            JOIN courses co ON ca.course_id = co.id 
            WHERE ca.student_id = %s AND ca.course_id = %s
            ORDER BY ca.date DESC
            """,
            (student['id'], course_id)
        )
        attendance = cursor.fetchall()
        
        # Get course info for the header if attendance is empty
        cursor.execute("SELECT name, code FROM courses WHERE id=%s", (course_id,))
        course = cursor.fetchone()
        
        return render_template('student_attendance.html', student=student, attendance=attendance, course=course)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/course/<int:course_id>/assignments')
def student_course_assignments(course_id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        cursor.execute("SELECT name, code FROM courses WHERE id=%s", (course_id,))
        course = cursor.fetchone()
        
        cursor.execute("SELECT * FROM assignments WHERE class_id = %s AND teacher_id IN (SELECT teacher_id FROM class_subjects WHERE class_id = %s AND course_id = %s) ORDER BY due_date DESC", (student['class_id'], student['class_id'], course_id))
        assignments = cursor.fetchall()
        return render_template('student_assignments.html', student=student, assignments=assignments, course=course)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/student/fees')
def student_fees():
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'student':
        student = get_student_by_username(session['username'])
        cursor.execute("SELECT * FROM fees WHERE student_id=%s", (student['id'],))
        fees = cursor.fetchall()
        return render_template('student_fees.html', student=student, fees=fees)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/add', methods=['GET', 'POST'])
def add_course():
    db = get_db()
    cursor = db.cursor()
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
                    "INSERT INTO courses (name, code, credit_hours, theory_hours, practical_hours, department) VALUES (%s, %s, %s, %s, %s, %s)",
                    (name, code, credit_hours, theory_hours, practical_hours, department)
                )
                db.commit()
                flash(f"Course '{name}' added successfully.", "success")
                return redirect(url_for('view_courses'))
            except psycopg2.IntegrityError:
                flash("Course code must be unique.", "danger")
        return render_template('admin_add_course.html')
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/edit/<int:id>', methods=['GET', 'POST'])
def edit_course(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("SELECT * FROM courses WHERE id=%s", (id,))
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
                    "UPDATE courses SET name=%s, code=%s, credit_hours=%s, theory_hours=%s, practical_hours=%s, department=%s WHERE id=%s",
                    (name, code, credit_hours, theory_hours, practical_hours, department, id)
                )
                db.commit()
                flash("Course updated successfully.", "success")
                return redirect(url_for('view_courses'))
            except psycopg2.IntegrityError:
                flash("Course code must be unique.", "danger")
        return render_template('admin_edit_course.html', course=course)
    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))


@app.route('/admin/courses/delete/<int:id>', methods=['POST'])
def delete_course(id):
    db = get_db()
    cursor = db.cursor()
    if 'role' in session and session['role'] == 'admin':
        cursor.execute("DELETE FROM courses WHERE id=%s", (id,))
        db.commit()
        flash("Course deleted successfully!", "success")
        return redirect(url_for('view_courses'))
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
