from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import sqlite3
import csv
import io
from pathlib import Path
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "change-this-secret-before-deployment"
DB = Path(__file__).with_name("school.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll_no TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        course TEXT NOT NULL,
        year INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        department TEXT NOT NULL,
        phone TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
        UNIQUE(student_id, attendance_date),
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_date TEXT NOT NULL,
        description TEXT DEFAULT '',
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)
    con.commit()
    con.close()
    
# Create database tables when the application starts
init_db()

@app.route("/")
def dashboard():
    con = db()

    students = con.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    teachers = con.execute(
        "SELECT COUNT(*) FROM teachers"
    ).fetchone()[0]

    courses = con.execute(
        "SELECT COUNT(DISTINCT course) FROM students"
    ).fetchone()[0]

    today = date.today()
    today_text = today.isoformat()

    total_today = con.execute(
        "SELECT COUNT(*) FROM attendance WHERE attendance_date=?",
        (today_text,)
    ).fetchone()[0]

    present_today = con.execute(
        """SELECT COUNT(*) FROM attendance
           WHERE attendance_date=? AND status='Present'""",
        (today_text,)
    ).fetchone()[0]

    attendance_pct = (
        round(present_today * 100 / total_today)
        if total_today else 0
    )

    # Last 7 days attendance
    week_start = today - timedelta(days=6)

    weekly_rows = con.execute("""
        SELECT attendance_date,
               COUNT(*) AS total_marked,
               SUM(CASE WHEN status='Present'
                   THEN 1 ELSE 0 END) AS present_count
        FROM attendance
        WHERE attendance_date BETWEEN ? AND ?
        GROUP BY attendance_date
    """, (week_start.isoformat(), today_text)).fetchall()

    weekly_lookup = {
        row["attendance_date"]: round(
            row["present_count"] * 100 / row["total_marked"]
        )
        for row in weekly_rows
        if row["total_marked"] > 0
    }

    weekly_labels = []
    weekly_attendance = []

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        weekly_labels.append(current_day.strftime("%a"))
        weekly_attendance.append(
            weekly_lookup.get(current_day.isoformat())
        )

    fee_total = con.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fees"
    ).fetchone()[0]

    recent_students = con.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 5"
    ).fetchall()

    recent_fees = con.execute("""
        SELECT fees.*, students.name, students.roll_no
        FROM fees
        JOIN students ON students.id=fees.student_id
        ORDER BY fees.id DESC LIMIT 4
    """).fetchall()

    con.close()

    has_weekly_attendance = any(
        value is not None for value in weekly_attendance
    )

    return render_template(
        "dashboard.html",
        students=students,
        teachers=teachers,
        courses=courses,
        attendance_pct=attendance_pct,
        fee_total=fee_total,
        recent_students=recent_students,
        recent_fees=recent_fees,
        weekly_labels=weekly_labels,
        weekly_attendance=weekly_attendance,
        has_weekly_attendance=has_weekly_attendance
    )


@app.route("/students")
def students():
    q = request.args.get("q", "").strip()
    con = db()
    rows = con.execute("""
        SELECT * FROM students
        WHERE name LIKE ? OR roll_no LIKE ? OR course LIKE ?
        ORDER BY id DESC
    """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    con.close()
    return render_template("students.html", rows=rows, q=q)

@app.route("/students/add", methods=["GET", "POST"])
def student_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll = request.form.get("roll_no", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        try:
            year = int(request.form.get("year", ""))
            if not all([name, roll, email, course]) or year not in range(1, 7):
                raise ValueError
            con = db()
            con.execute("INSERT INTO students(name,roll_no,email,course,year) VALUES(?,?,?,?,?)",
                        (name, roll, email, course, year))
            con.commit()
            con.close()
            flash("Student added successfully.", "success")
            return redirect(url_for("students"))
        except ValueError:
            flash("Enter all fields and a valid academic year.", "danger")
        except sqlite3.IntegrityError:
            flash("That roll number already exists.", "danger")
    return render_template("student_form.html", row=None)

@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
def student_edit(sid):
    con = db()
    row = con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not row:
        con.close()
        flash("Student not found.", "danger")
        return redirect(url_for("students"))
    if request.method == "POST":
        try:
            year = int(request.form.get("year", ""))
            values = [request.form.get(k, "").strip() for k in ("name","roll_no","email","course")]
            if not all(values) or year not in range(1, 7):
                raise ValueError
            con.execute("UPDATE students SET name=?,roll_no=?,email=?,course=?,year=? WHERE id=?",
                        (*values, year, sid))
            con.commit()
            con.close()
            flash("Student updated.", "success")
            return redirect(url_for("students"))
        except ValueError:
            flash("Enter all fields and a valid academic year.", "danger")
        except sqlite3.IntegrityError:
            flash("That roll number is already in use.", "danger")
    con.close()
    return render_template("student_form.html", row=row)

@app.post("/students/<int:sid>/delete")
def student_delete(sid):
    con = db()
    con.execute("DELETE FROM students WHERE id=?", (sid,))
    con.commit()
    con.close()
    flash("Student deleted.", "success")
    return redirect(url_for("students"))

@app.route("/teachers")
def teachers():
    con = db()
    rows = con.execute("SELECT * FROM teachers ORDER BY id DESC").fetchall()
    con.close()
    return render_template("teachers.html", rows=rows)

@app.route("/teachers/add", methods=["GET", "POST"])
def teacher_add():
    if request.method == "POST":
        values = [request.form.get(k, "").strip() for k in ("name","email","department","phone")]
        if not all(values[:3]):
            flash("Name, email and department are required.", "danger")
        else:
            con = db()
            con.execute("INSERT INTO teachers(name,email,department,phone) VALUES(?,?,?,?)", values)
            con.commit()
            con.close()
            flash("Teacher added successfully.", "success")
            return redirect(url_for("teachers"))
    return render_template("teacher_form.html")

@app.post("/teachers/<int:tid>/delete")
def teacher_delete(tid):
    con = db()
    con.execute("DELETE FROM teachers WHERE id=?", (tid,))
    con.commit()
    con.close()
    flash("Teacher deleted.", "success")
    return redirect(url_for("teachers"))

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    selected = request.values.get("attendance_date", date.today().isoformat())
    con = db()
    if request.method == "POST":
        for student in con.execute("SELECT id FROM students").fetchall():
            status = request.form.get(f"status_{student['id']}")
            if status in ("Present", "Absent"):
                con.execute("""
                    INSERT INTO attendance(student_id,attendance_date,status)
                    VALUES(?,?,?)
                    ON CONFLICT(student_id,attendance_date)
                    DO UPDATE SET status=excluded.status
                """, (student["id"], selected, status))
        con.commit()
        flash("Attendance saved.", "success")
    rows = con.execute("""
        SELECT students.*,
        (SELECT status FROM attendance
         WHERE attendance.student_id=students.id AND attendance.attendance_date=?) AS status
        FROM students ORDER BY students.name
    """, (selected,)).fetchall()
    con.close()
    return render_template("attendance.html", rows=rows, selected=selected)

@app.route("/fees", methods=["GET", "POST"])
def fees():
    con = db()
    if request.method == "POST":
        try:
            sid = int(request.form.get("student_id", ""))
            amount = float(request.form.get("amount", ""))
            payment_date = request.form.get("payment_date", date.today().isoformat())
            description = request.form.get("description", "").strip()
            if amount <= 0:
                raise ValueError
            con.execute("INSERT INTO fees(student_id,amount,payment_date,description) VALUES(?,?,?,?)",
                        (sid, amount, payment_date, description))
            con.commit()
            flash("Fee payment recorded.", "success")
            con.close()
            return redirect(url_for("fees"))
        except (ValueError, sqlite3.IntegrityError):
            flash("Enter a valid student and positive payment amount.", "danger")
    student_rows = con.execute("SELECT id,name,roll_no FROM students ORDER BY name").fetchall()
    payments = con.execute("""
        SELECT fees.*, students.name, students.roll_no
        FROM fees JOIN students ON students.id=fees.student_id
        ORDER BY fees.payment_date DESC, fees.id DESC
    """).fetchall()
    total = con.execute("SELECT COALESCE(SUM(amount),0) FROM fees").fetchone()[0]
    con.close()
    return render_template("fees.html", students=student_rows, payments=payments, total=total, today=date.today().isoformat())

@app.route("/reports")
def reports():
    con = db()
    by_course = con.execute("SELECT course, COUNT(*) AS total FROM students GROUP BY course ORDER BY total DESC").fetchall()
    total_students = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_teachers = con.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
    total_fees = con.execute("SELECT COALESCE(SUM(amount),0) FROM fees").fetchone()[0]
    con.close()
    return render_template("reports.html", by_course=by_course, total_students=total_students,
                           total_teachers=total_teachers, total_fees=total_fees)

@app.route("/reports/students.csv")
def export_students():
    con = db()
    rows = con.execute("SELECT name,roll_no,email,course,year FROM students ORDER BY name").fetchall()
    con.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Roll Number", "Email", "Course", "Year"])
    writer.writerows([tuple(row) for row in rows])
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=students_report.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
