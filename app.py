from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from db import get_connection

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


# ==================Home Routes =======================

@app.route("/")
def index():
    if "user_id" in session:  # redirect to dashboard or login
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ================REGISTER=========================

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


#=================LOGIN====================
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


# =========DASHBOARD — protected page(requires login)=====

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# ==================== RUN THE APP ======================
# debug= True means Flask shows helpful errors in the browser
# Remove debug=True before deploying to Railway

if __name__ == "__main__":
    app.run(debug=True)