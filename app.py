from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from db import get_connection
from priority import compute_priority_score 
from datetime import datetime
import json

# Load secrets pass variables from .env
load_dotenv()

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")


# =====================AUTH DECORATOR=============================

def login_required(f): # Put @login_required above any route that needs a logged-in user.
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session: # If the user is not logged in, automatically send them to login .
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Funtion names: add_task, complet_taks, delete_task, edit_task, dashboard, register, login, logout
# Routes include <int:task_id> for the task-specific actions (complete, delete, edit).
# Each route ends by redirecting to the dashboard
# ==================Home Route =======================

@app.route("/")
def index():
    if "user_id" in session:  # redirect to dashboard or login
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ================REGISTER Route=========================

# GET - show the registration form
# POST - process the form, create the user, redirect to login

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        # Hash the password — never stores the real one
        hashed_password = generate_password_hash(password)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (email, hashed_password)
            )
            conn.commit()
            return redirect(url_for("login"))

        except Exception:
            # This fires if the email already exists (UNIQUE constraint)
            return render_template("register.html", error="That email is already registered.")

        finally:
            cursor.close()
            conn.close()

    # GET request — just show the form
    return render_template("register.html")


#=================LOGIN route ====================
# GET - show the login form
# POST -check credentials, create session, redirect to dashboard

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)  # returns rows as dicts, not tuples
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # Check: does user exist AND does the hash match?
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Incorrect email or password.")

    return render_template("login.html")


# ==============LOGOUT==================
# Clears the session (forgets who is logged in) and goes to login

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

 #====================Add Task route============
@app.route("/add_task", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form["title"].strip()
        deadline = request.form["deadline"] or None
        priority = int(request.form.get("priority", 2))
        estimate_mins = int(request.form.get("estimate_mins", 25))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (user_id, title, deadline, priority, estimate_mins)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session["user_id"], title, deadline, priority, estimate_mins)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect(url_for("dashboard"))

    return render_template("task_form.html", task=None)  # task=None indicates this is a new task, not editing an existing one)   

#====================complete task route=========================
@app.route("/tasks/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tasks
        SET is_complete = 1
        WHERE id = %s AND user_id = %s
        """,
        (task_id, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect (url_for("dashboard"))

#===============Delete task route=================
@app.route("/tasks/<int:task_id>/delete")
@login_required
def delete_task(task_id):
    conn= get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM tasks
        WHERE id = %s AND user_id = %s
        """,
        (task_id, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))


# =========DASHBOARD — protected page(requires login)=====

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, title, deadline, priority, estimate_mins, is_complete
        FROM tasks
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )
    tasks = cursor.fetchall()

    cursor.close()
    conn.close()

    # adding a computed score to each task 
    for t in tasks:
        t["score"] = compute_priority_score(t)
    # sort by score descending, then by id
    tasks.sort(key=lambda t: (-t["score"], t["id"]))

    return render_template("dashboard.html", tasks=tasks)

    # just pass tasks, will add scorring later 
    return render_template("dashboard.html", tasks=tasks)

# ====================TASK EDIT==========
@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch the task first
    cursor.execute(
        """
        SELECT id, title, deadline, priority, estimate_mins
        FROM tasks
        WHERE id= %s AND user_id= %s
        """,
        (task_id, session["user_id"])
    )
    task = cursor.fetchone()

    if not task:
        cursor.close()
        conn.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form["title"].strip()
        deadline = request.form["deadline"] or None
        priority = int(request.form.get("priority", 2))
        estimate_mins = int(request.form.get("estimate_mins", 25))

        cursor.execute(
            """
            UPDATE tasks
            SET title=%s, deadline=%s, priority=%s, estimate_mins=%s
            WHERE id=%s AND user_id=%s
            """,
            (title, deadline, priority, estimate_mins, task_id, session["user_id"])
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for("dashboard"))

    cursor.close()
    conn.close()
    return render_template("task_form.html", task=task)

#==========focus Session route=========================
# session_date will auto-fill with today's date thanks to its default.
@app.route("/focus/log", methods=["POST"])
@login_required
def log_focus():
    data = request.get_json(force=True)
    task_id = int(data.get("task_id"))
    duration_mins = int(data.get("duration_mins"))

    elapsed_secs = duration_mins * 60 # converts minutes to seconds for database storage

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO focus_sessions (user_id, task_id, elapsed_secs, completed) 
        VALUES (%s, %s, %s, %s)
        """,
        (session["user_id"], task_id, elapsed_secs, 1)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return ("", 204)  # empty success response

# ==================== RUN THE APP ======================
# debug= True means Flask shows helpful errors in the browser
# Remove debug=True before deploying to Railway

if __name__ == "__main__":
    app.run(debug=True)