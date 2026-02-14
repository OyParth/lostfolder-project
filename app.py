from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallbacksecret")


DATABASE = "database.db"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        location TEXT,
        type TEXT,
        image TEXT,
        status TEXT DEFAULT 'Pending'
    )
    """)

    conn.commit()
    conn.close()


# ================= HELPERS =================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper


# ================= HOME =================
@app.route("/")
def home():
    return render_template("index.html")


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = generate_password_hash(request.form["password"])

        role = "admin" if username == "parth" else "user"

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
            conn.commit()
            flash("Account created successfully!")
            return redirect(url_for("login"))
        except:
            flash("Username already exists!")

    return render_template("register.html")


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful!")

            if user["role"] == "admin":
                return redirect(url_for("admin"))
            else:
                return redirect(url_for("home"))
        else:
            flash("Invalid credentials")

    return render_template("login.html")


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for("home"))


# ================= DASHBOARD =================
@app.route("/items")
@login_required
def dashboard():
    conn = get_db()
    items = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    return redirect(url_for("index"))


# ================= REPORT LOST =================
@app.route("/report/lost", methods=["GET", "POST"])
@login_required
def report_lost():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]

        image_file = request.files.get("image")
        filename = None

        if image_file and image_file.filename != "":
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            else:
                flash("Invalid image format!")
                return redirect(request.url)

        conn = get_db()
        conn.execute("""
            INSERT INTO items (title, description, location, type, image)
            VALUES (?, ?, ?, 'Lost', ?)
        """, (title, description, location, filename))
        conn.commit()

        flash("Lost item reported successfully!")
        return redirect(url_for("dashboard"))

    return render_template("add_lost.html")


# ================= REPORT FOUND =================
@app.route("/report/found", methods=["GET", "POST"])
@login_required
def report_found():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]

        image_file = request.files.get("image")
        filename = None

        if image_file and image_file.filename != "":
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            else:
                flash("Invalid image format!")
                return redirect(request.url)

        conn = get_db()
        conn.execute("""
            INSERT INTO items (title, description, location, type, image)
            VALUES (?, ?, ?, 'Found', ?)
        """, (title, description, location, filename))
        conn.commit()

        flash("Found item reported successfully!")
        return redirect(url_for("dashboard"))

    return render_template("add_found.html")


# ================= DELETE ITEM =================
@app.route("/delete/<int:item_id>")
@admin_required
def delete_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    flash("Item deleted successfully")
    return redirect(url_for("dashboard"))


# ================= ADMIN PANEL =================
@app.route("/admin")
@admin_required
def admin():
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    items = conn.execute("SELECT * FROM items").fetchall()
    return render_template("admin.html", users=users, items=items)


# ================= EXPORT EXCEL =================
@app.route("/export")
@admin_required
def export_excel():
    conn = get_db()
    items = conn.execute("SELECT * FROM items").fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Title", "Description", "Location", "Type", "Status"])

    for item in items:
        ws.append([
            item["id"],
            item["title"],
            item["description"],
            item["location"],
            item["type"],
            item["status"]
        ])

    file_path = "items.xlsx"
    wb.save(file_path)

    return send_file(file_path, as_attachment=True)


# ================= RUN =================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
