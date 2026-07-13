from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from google import genai
import os
from dotenv import load_dotenv

load_dotenv() # MUST run BEFORE reading any os.getenv(...)
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

from breakdown import get_task_breakdown
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from db import get_connection
from priority import compute_priority_score 
from datetime import datetime
from datetime import date
from datetime import date, timedelta
import json

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
            session["energy_level"] = user.get("energy_level", 3)
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
    cursor.execute(
        "UPDATE users SET energy_level = %s WHERE id = %s",
        (energy, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    labels = {1: "Exhausted ", 2: "Low ", 3: "Okay ", 4: "Good ", 5: "Energised "}
    flash(f"Energy updated to {labels[energy]} Tasks re-ranked!", "success")

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
    Brain Dump needs only a tile. Optional: may also send deadline, timeframe, estimate_mins.
    Always returns instantly with sensible silent defaults.
    """
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"success": False, "error": "Title is required."}), 400
    deadline = data.get("deadline") or None
    timeframe = data.get("timeframe") # today , week none, none
    estimate_mins = data.get("estimate_mins") or None

    # Map timeframe - deadline + priority, only if no explicit date was given
    if not deadline and timeframe:
        today = date.today()
        if timeframe == "today":
            deadline= today
            priority = 3
        elif timeframe == "week":
            deadline = today + timedelta(days=7)
            priority = 2
        else:    # "none" - No rush
            deadline = None
            priority = 1
    else:
        priority = 2    # neutral default when nothing was chosen at all

    conn= get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (user_id, title, deadline, priority, estimate_mins)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (session["user_id"], title, deadline, priority, estimate_mins)
    )
    conn.commit()
    new_task_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({"success": True, "task_id": new_task_id})




 #====================Add Task route============
@app.route("/add_task", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        deadline = request.form.get("deadline") or None
        priority = int(request.form.get("priority", 2))
        estimate_mins = int(request.form.get ("estimate_mins", 25))#
        if not title:
            flash ("Task title is required.", "danger")
            return redirect(url_for("add_task"))

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

#====== All_tasks=====================
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
#=============COACH GENAI ROUTE==================

@app.route("/tasks/<int:task_id>/coach", methods=["POST"])
@login_required
def coach_tip(task_id):
    data = request.get_json(force=True)
    title = data.get("title", "this task")
    deadline = data.get("deadline") or "not set deadline"
    priority = data.get("priority", 2)
    prompt = (
        f"A user with ADHD feels stuck starting this task: '{title}' ."
        f"Deadline: {deadline}.Priority level: {priority} (1=low, 3=high). "
        "Break down this task into thiny manageable steps, concrete first action they could do in under the deadline in minutes. "
        "keep it under 20 words. No generic advice like 'just start' - be specific."
    )
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        tip = response.text.strip()
    except Exception as e:
        print("Gemini error:", e)
        tip = "Open the task and write just one sentence or step. That's the whole goal for now. "

    return jsonify({"tip": tip})

# ======BREAKDOWN Route =======
@app.route("/tasks/<int:task_id>/breakdown", methods=["POST"])
@login_required
def task_breakdown(task_id):
    
    """
    Returns a JSON breakdown of micro-steps for a stuck user.
    Called via fetch() from dashboard.html and all_tasks.html.
    """
    data = request.get_json(force=True)

    title = data.get("title", "this task")
    deadline = data.get("deadline") or None
    priority = int(data.get("priority", 2))
    estimate_mins = int(data.get("estimate_mins", 25))
    energy_level = session.get("energy_level", 3)   # from session set by /set_energy

    result = get_task_breakdown(
        title=title,
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
        """
        SELECT * FROM tasks
        WHERE user_id = %s AND is_complete = 0
        """,
        (session["user_id"],)
    )
    tasks = cursor.fetchall()

    
# Query2: get todays toatal focus time
    cursor.execute(
        """
        SELECT SUM(elapsed_secs) AS total_secs
        FROM focus_sessions
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    tasks = cursor.fetchall()

# Query 2: get todya's total focus time ( before closing, e.g cursor/conn.close)
    cursor.execute( #sends the question to MysQL to get the total time spent on focus sessions for the logged-in user
    
        """
        SELECT SUM(elapsed_secs) AS total_secs
        FROM focus_sessions
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )
    result = cursor.fetchone() # grabs the single row answer ( there is only one, since SUM adds wvweything into one number)
    total_secs = result["total_secs"] or 0 # if no focus sesssions today, SUM returns None. this is a safety net,i.e. if user has no focus today SUM() returns null and Py crashes trying to maths on None. The "or 0" says: if empty, just treat it as 0.
    total_focus_minutes = total_secs // 60
# Query 3: get distinct days user has focused ( for streak calculaton)
    cursor.execute(
        """
        SELECT DISTINCT session_date
        FROM focus_sessions
        WHERE user_id = %s
        ORDER BY session_date DESC
        """,
        (session["user_id"],)

    )
    result = cursor.fetchone()
    total_secs= result["total_secs"] or 0
    total_focus_minutes = total_secs // 60

    # query 3 : distinct foucs days for streak
    cursor.execute(
        """
        SELECT DISTINCT session_date
        FROM focus_sessions
        WHERE user_id = %s
        ORDER BYsession_date DESC
        """,
        (session["user_id"],)
    )
    focus_days = [row["session_date"] for row in cursor.fetchall()]

#Now I can close - after all queries are done
    cursor.close()
    conn.close()
# adding the streak calculation
       
    streak = 0 
    expected_day = date.today()

    for day in focus_days:
        if day == expected_day:
            streak += 1
            expected_day = expected_day - timedelta (days=1)
        else:
            break

# Score every task, then sort, then slice to top 3
#Raking is : urgency (exponential decay), importance (priority 1–3), and energy-fit all feeding into one real score, sorted, then sliced to 3 
    energy_level = session.get("energy_level", 3 ) # default is 3
    for t in tasks:
        t["score"] = compute_priority_score(t, energy_level=energy_level)
    tasks.sort(key=lambda t: (-t["score"], t["id"])) # sort by score descending, then by id
    tasks = tasks[:3]   # slice after scoring, not before

    return render_template(
        "dashboard.html",
        tasks=tasks,
        total_focus_minutes=total_focus_minutes,
        streak=streak
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