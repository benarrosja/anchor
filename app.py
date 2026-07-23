from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import os
import random
import mysql.connector  # needed to catch IntegrityError in register()
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

load_dotenv() # must run before reading any os.getenv

from breakdown import get_task_breakdown
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from db import get_connection
from priority import compute_priority_score 


# Create the Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

BADGES = [
    (1, "Seedling"), (3, "Sprout"), (7, "Flame"),
    (14, "Star"), (30, "Trophy"), (60, "Gem"), (100, "Crown")
]
ENCOURAGEMENT_QUOTES = [
    "Progress, not perfection.",
    "Small steps still move you forward.",
    "You showed up today - that counts.",
    "Consistency beats intensity.",
    "One task at a time is enough.",
    "Find motivation in what you do and you will never feel tired again.",
    "It is all about the journey, not the destination.",
]

ENERGY_LABELS = {
    1: "Exhausted", 2: "Low", 3: "Okay", 4: "Good", 5: "Energised"
}


# =====================AUTH DECORATOR=============================

def login_required(f): # Put @login_required above any route that needs a logged-in user.
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session: # If the user is not logged in, automatically send them to login .
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ==================Home Route ====

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


        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters."
            )

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

        except mysql.connector.errors.IntegrityError:
            return render_template("register.html", error="That email is already registered.")
        except Exception as e:
            print("Register error:", e)
            return render_template(
            "register.html",
            error="Something went wrong creating your account. Please try again."
            )
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
            session["energy_level"] = user.get("energy_level") or 3
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Incorrect email or password.")

    return render_template("login.html")

#====================SET ENERGY ROUTE
@app.route("/set_energy", methods=["POST"])
@login_required
def set_energy():
    energy = int(request.form.get("energy", 3))
    energy = max(1, min(5, energy)) # clamp to 1-5 range

    # saving to session (immediat effect on scoring)
    session["energy_level"] = energy

    # persist to DB so it survices page reloads
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET energy_level = %s WHERE id = %s",
            (energy, session["user_id"])
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()
    flash(f"Energy updated to {ENERGY_LABELS[energy]} - Tasks re-ranked!", "success")
    return redirect(url_for("dashboard"))



# ==============LOGOUT==================
# Clears the session (forgets who is logged in) and goes to login

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ====Quick  Add ( Brain Dump) route========
@app.route("/quick_add_task", methods =["POST"])
@login_required
def quick_add_task():
    """
    Brain Dump only needs a title. Optional: deadline, timeframe, estimate_mins, details. 
    Returns JSON so the JS can confirm without a page reload.
    """
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"success": False, "error": "Title is required."}), 400
        
    details = (data.get("details") or "").strip() or None
    raw_deadline = (data.get("deadline") or "").strip()
    timeframe = (data.get("timeframe") or "none").strip()
    estimate_mins = data.get("estimate_mins") or 25

    # Map timeframe - deadline + priority, only if no explicit date was given
    try:
        estimate_mins = int(estimate_mins)
        if estimate_mins < 1:
            estimate_mins = 25
    except (TypeError, ValueError):
        estimate_mins = 25

    deadline = None
    priority = 2

    if raw_deadline:
        try:
            deadline = datetime.strptime(raw_deadline, "%Y-%m-%d").date()
            days_until_due = (deadline - date.today()).days
            if days_until_due <= 0:
                priority = 3
            elif days_until_due <= 7:
                priority = 2
            else:
                priority = 1
        except ValueError:
            return jsonify({"success": False, "error": "Invalid deadline format."}), 400

    elif timeframe == "today":
        deadline = date.today()
        priority = 3
    elif timeframe == "week":
        deadline = date.today() + timedelta(days=7)
        priority = 2
    else:
       deadline = None
       priority = 1

    conn= get_connection()
    cursor = conn.cursor()
    try:
        
        cursor.execute(
            """
            INSERT INTO tasks (user_id, title, deadline, priority, estimate_mins, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session["user_id"], title, deadline, priority, estimate_mins, details)
        )
        conn.commit()
        new_task_id = cursor.lastrowid      
    finally:
        cursor.close()
        conn.close()

    return jsonify({"success": True, "task_id": new_task_id})


 #====================Add Task route============
@app.route("/add_task", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Task title is required.", "danger")
            return redirect(url_for("add_task"))

        deadline = request.form.get("deadline") or None
        priority = int(request.form.get("priority", 2))
        estimate_mins = int(request.form.get ("estimate_mins", 25))
        details = request.form.get("details", "").strip() or None

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
            """
            INSERT INTO tasks (user_id, title, deadline, priority, estimate_mins, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session["user_id"], title, deadline, priority, estimate_mins, details)
            )
            conn.commit()
        
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for("dashboard"))

    return render_template("task_form.html", task=None)  # task=None indicates this is a new task, not editing an existing one)   

#====== All_tasks
@app.route("/tasks")
@login_required
def all_tasks():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT *
        FROM tasks
        WHERE user_id = %s
        ORDER BY is_complete ASC, priority DESC, deadline ASC, id DESC
        """,
        (session["user_id"],)
    )

    tasks = cursor.fetchall()
    
    cursor.close()
    conn.close()

    today = date.today()
    next_week = today + timedelta(days=7)
    
    overdue_tasks = []
    due_soon_tasks = []
    later_tasks = []
    completed_tasks = []

    for task in tasks:
        if task["is_complete"]:
            completed_tasks.append(task)
        elif task["deadline"]:
            if task["deadline"] < today:
                overdue_tasks.append(task)
            elif task["deadline"] <= next_week:
                due_soon_tasks.append(task)
            else:
                later_tasks.append(task)
        else:
            later_tasks.append(task)
        
    return render_template(
        "all_tasks.html",
        overdue_tasks=overdue_tasks,
        due_soon_tasks=due_soon_tasks,
        later_tasks=later_tasks,
        completed_tasks=completed_tasks
        )

#========complete task route
@app.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_task(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
       cursor.execute(
           "UPDATE tasks SET is_complete = 1 WHERE id = %s AND user_id = %s",
           (task_id, session["user_id"])
       )
       conn.commit()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("dashboard"))


#===============Delete task route=================
@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    conn= get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, session["user_id"])
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("dashboard"))

#====== Pin Route===========
@app.route("/tasks/<int:task_id>/pin", methods=["POST"])
@login_required
def toggle_pin(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE tasks SET pinned_to_top = NOT pinned_to_top WHERE id = %s AND user_id = %s",
            (task_id, session["user_id"])
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("all_tasks"))

@app.route("/tasks/<int:task_id>/update_details", methods=["POST"])
@login_required
def update_task_details(task_id):
    data = request.get_json(force=True)
    details = (data.get("details") or "").strip() or None
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE tasks SET details = %s WHERE id = %s AND user_id = %s",
            (details, task_id, session["user_id"])
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify({"success": True})


# ======BREAKDOWN Route =======
@app.route("/tasks/<int:task_id>/breakdown", methods=["POST"])
@login_required
def task_breakdown(task_id):
    data = request.get_json(force=True)

    title = data.get("title", "this task")
    details = data.get("details") or None
    deadline = data.get("deadline") or None
    priority = int(data.get("priority", 2))
    estimate_mins = int(data.get("estimate_mins", 25))
    energy_level = session.get("energy_level") or 3

    result = get_task_breakdown(
        title=title,
        details=details,
        deadline=deadline,
        priority=priority,
        estimate_mins=estimate_mins,
        energy_level=energy_level
    )

    return jsonify(result)


# =========DASHBOARD-Route protected page(requires login)=====

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
#Query 1-  Fetch all incomplete tasks - no limit, score first slice later 
# the true ranking depends on comput_priorty_score(), not MSQL order 
    cursor.execute(
        "SELECT * FROM tasks WHERE user_id = %s AND is_complete = 0",
        (session["user_id"],)
    )
    tasks = cursor.fetchall()

    
# Query2: get todays toatal focus time
    cursor.execute(
        " SELECT SUM(elapsed_secs) AS total_secs FROM focus_sessions WHERE user_id = %s",
        (session["user_id"],)
    )

    result = cursor.fetchone()
    total_secs = result["total_secs"] or 0
    total_focus_minutes = total_secs // 60


    # query 2 : distinct foucs days for streak
    cursor.execute(
        "SELECT total_active_days,last_active_date  FROM users WHERE id = %s",
        (session["user_id"],))
    user_row = cursor.fetchone()
    total_active_days = user_row["total_active_days"] or 0
    last_active_date = user_row["last_active_date"]
    
    cursor.close()
    conn.close()


    today = date.today()
    if last_active_date != today:
        total_active_days += 1
        conn2 = get_connection()
        cursor2 = conn2.cursor()
        try:
            cursor2.execute(
            "UPDATE users SET total_active_days = %s, last_active_date = %s WHERE id = %s",
            (total_active_days, today, session["user_id"])
        )
            conn2.commit()
        finally:
            cursor2.close()
            conn2.close()

    # Badge milestones — never resets, only grows to motivate ADHD users
    current_badge = "Seedling"
    for days_required, label in BADGES:
        if total_active_days >= days_required:
            current_badge = label

   
    today_quote = random.choice(ENCOURAGEMENT_QUOTES)

# Score every task, then sort, then slice to top 3
#Raking is : urgency (exponential decay), importance (priority 1–3), and energy-fit all feeding into one real score, sorted, then sliced to 3 
    energy_level = session.get("energy_level") or 3
    for t in tasks:
        t["score"] = compute_priority_score(t, energy_level=energy_level) or 0.0 # The or 0.0 ensures that even in some unforeseen edge case, t["score"] is always a real number before .sort() runs
    
        
    pinned_tasks = [t for t in tasks if t.get("pinned_to_top")]
    other_tasks = [t for t in tasks if not t.get("pinned_to_top")]
    pinned_tasks.sort(key=lambda t: (-t["score"], t["id"]))
    other_tasks.sort(key=lambda t: (-t["score"], t["id"]))
    tasks = (pinned_tasks + other_tasks)[:3]

    return render_template(
        "dashboard.html",
        tasks=tasks,
        total_focus_minutes= total_focus_minutes,
        total_active_days= total_active_days,
        current_badge= current_badge,
        today_quote= today_quote,

    )


# ====================TASK EDIT==========
@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch the task first
    cursor.execute(
        """
        SELECT id, title, deadline, priority, estimate_mins, details FROM tasks
        WHERE id= %s AND user_id= %s
        """,
        (task_id, session["user_id"])
    )
    task = cursor.fetchone()
    cursor.close()
    conn.close()

    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":        
        title = request.form["title"].strip()
        details = request.form.get("details", "").strip() or None
        deadline = request.form.get("deadline") or None
        priority = int(request.form.get("priority", 2))
        estimate_mins = int(request.form.get("estimate_mins", 25))

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE tasks
                SET title=%s, details=%s, deadline=%s, priority=%s, estimate_mins=%s
                WHERE id=%s AND user_id=%s
                """,
                (title, details, deadline, priority, estimate_mins, task_id, session["user_id"])
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        flash("Task updated.", "success")
        return redirect(url_for("dashboard"))

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

    try:
        cursor.execute("SELECT id FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"]))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return ("", 403)
        
        cursor.execute(
            """
        INSERT INTO focus_sessions (user_id, task_id, elapsed_secs, completed) 
        VALUES (%s, %s, %s, %s)
        """,
        (session["user_id"], task_id, elapsed_secs, 1)
    
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return ("", 204)  # empty success response

# ==================== RUN THE APP ======================
# debug= True means Flask shows helpful errors in the browser
# Remove debug=True before deploying to Railway

if __name__ == "__main__":
    app.run(debug=True)