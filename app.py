import os
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import inspect, text


# LOAD ENVIRONMENT VARIABLES
load_dotenv()

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    instance_relative_config=True
)
os.makedirs(app.instance_path, exist_ok=True)


# APPLICATION CONFIGURATION
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is missing from environment variables.")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + str(Path(app.instance_path) / "helpdesk.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# INITIALIZE EXTENSIONS
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

csrf = CSRFProtect(app)


# SLA TARGETS IN HOURS
SLA_HOURS = {
    "Critical": 4,
    "High": 8,
    "Medium": 24,
    "Low": 72
}


# USER MODEL
class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# TICKET MODEL
class Ticket(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(30), default="Open")

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    sla_deadline = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref="tickets"
    )

    assigned_staff = db.relationship(
        "User",
        foreign_keys=[assigned_to_id]
    )


# STAFF ACCESS CONTROL
def staff_required(function):

    @wraps(function)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.role != "staff":
            flash("Access denied. Staff only.", "error")
            return redirect(url_for("dashboard"))

        return function(*args, **kwargs)

    return decorated_function


# LOAD LOGGED-IN USER
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# DATABASE SETUP AND SAFE MIGRATION
with app.app_context():

    db.create_all()

    # Check existing ticket table columns
    columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("ticket")
    }

    migrations = {
        "assigned_to_id": "INTEGER",
        "sla_deadline": "DATETIME",
        "resolved_at": "DATETIME"
    }

    # Add missing columns to older databases
    with db.engine.begin() as connection:

        for column_name, column_type in migrations.items():

            if column_name not in columns:

                connection.execute(
                    text(
                        f"ALTER TABLE ticket ADD COLUMN "
                        f"{column_name} {column_type}"
                    )
                )

    # Add SLA deadlines to older tickets
    old_tickets = Ticket.query.filter(
        Ticket.sla_deadline.is_(None)
    ).all()

    for ticket in old_tickets:

        hours = SLA_HOURS.get(ticket.priority, 24)
        created = ticket.created_at or datetime.utcnow()

        ticket.sla_deadline = created + timedelta(hours=hours)

    db.session.commit()

    # CREATE OR UPDATE STAFF ACCOUNT FROM ENVIRONMENT VARIABLES
    staff_name = (os.getenv("STAFF_NAME") or "").strip()
    staff_email = (os.getenv("STAFF_EMAIL") or "").strip().lower()
    staff_password = os.getenv("STAFF_PASSWORD") or ""

    staff_settings = [
        staff_name,
        staff_email,
        staff_password
    ]

    # All three settings must be provided together
    if any(staff_settings) and not all(staff_settings):
        raise RuntimeError(
            "Set STAFF_NAME, STAFF_EMAIL, and STAFF_PASSWORD together."
        )

    # Create or update the configured staff account
    if all(staff_settings):

        if len(staff_password) < 12:
            raise RuntimeError(
                "STAFF_PASSWORD must contain at least 12 characters."
            )

        staff_user = User.query.filter_by(
            email=staff_email
        ).first()

        if staff_user is None:

            staff_user = User(
                name=staff_name,
                email=staff_email,
                role="staff"
            )

            staff_user.set_password(staff_password)
            db.session.add(staff_user)

        else:

            staff_user.name = staff_name
            staff_user.role = "staff"

            if not staff_user.check_password(staff_password):
                staff_user.set_password(staff_password)

        db.session.commit()


# HOME PAGE
@app.route("/")
def home():

    if current_user.is_authenticated:

        if current_user.role == "staff":
            return redirect(url_for("staff_dashboard"))

        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if len(password) < 12:
            flash(
                "Password must contain at least 12 characters.",
                "error"
            )
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        new_user = User(
            name=name,
            email=email,
            role="user"
        )

        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):

            login_user(user)

            flash("Login successful!", "success")

            if user.role == "staff":
                return redirect(url_for("staff_dashboard"))

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# USER DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():

    return render_template("dashboard.html")


# STAFF DASHBOARD
@app.route("/staff/dashboard")
@staff_required
def staff_dashboard():

    # Get all tickets
    all_tickets = Ticket.query.order_by(
        Ticket.created_at.desc()
    ).all()

    # Get search and filter values
    search_query = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "")
    selected_priority = request.args.get("priority", "")
    selected_status = request.args.get("status", "")

    # Start filtering
    query = Ticket.query

    # Search by ticket title
    if search_query:
        query = query.filter(
            Ticket.title.ilike(f"%{search_query}%")
        )

    # Filter by category
    if selected_category:
        query = query.filter(
            Ticket.category == selected_category
        )

    # Filter by priority
    if selected_priority:
        query = query.filter(
            Ticket.priority == selected_priority
        )

    # Filter by status
    if selected_status:
        query = query.filter(
            Ticket.status == selected_status
        )

    # Get filtered tickets
    tickets = query.order_by(
        Ticket.created_at.desc()
    ).all()

    # Ticket statistics
    total_tickets = len(all_tickets)

    open_tickets = sum(
        1 for ticket in all_tickets
        if ticket.status == "Open"
    )

    in_progress_tickets = sum(
        1 for ticket in all_tickets
        if ticket.status == "In Progress"
    )

    resolved_tickets = sum(
        1 for ticket in all_tickets
        if ticket.status == "Resolved"
    )

    # Category statistics
    categories = [
        "Network",
        "Hardware",
        "Software",
        "Account",
        "Other"
    ]

    category_counts = {
        category: sum(
            1 for ticket in all_tickets
            if ticket.category == category
        )
        for category in categories
    }

    # Priority statistics
    priorities = [
        "Critical",
        "High",
        "Medium",
        "Low"
    ]

    priority_counts = {
        priority: sum(
            1 for ticket in all_tickets
            if ticket.priority == priority
        )
        for priority in priorities
    }

    return render_template(
        "staff_dashboard.html",
        tickets=tickets,
        now=datetime.utcnow(),
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        category_counts=category_counts,
        priority_counts=priority_counts,
        search_query=search_query,
        selected_category=selected_category,
        selected_priority=selected_priority,
        selected_status=selected_status
    )


# STAFF REPORTS
@app.route("/staff/reports")
@staff_required
def staff_reports():

    tickets = Ticket.query.all()

    category_counts = {}
    issue_counts = {}

    for ticket in tickets:

        category = ticket.category
        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

        issue = ticket.title.strip()
        issue_key = issue.lower()

        if issue_key not in issue_counts:
            issue_counts[issue_key] = {
                "title": issue,
                "count": 0
            }

        issue_counts[issue_key]["count"] += 1

    category_reports = sorted(
        category_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )

    issue_reports = sorted(
        issue_counts.values(),
        key=lambda item: item["count"],
        reverse=True
    )

    return render_template(
        "staff_reports.html",
        total_tickets=len(tickets),
        category_reports=category_reports,
        issue_reports=issue_reports
    )


# CREATE TICKET
@app.route("/create-ticket", methods=["GET", "POST"])
@login_required
def create_ticket():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "")
        priority = request.form.get("priority", "Medium")

        if not title or not description or not category:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("create_ticket"))

        if priority not in SLA_HOURS:
            priority = "Medium"

        created_time = datetime.utcnow()

        sla_deadline = created_time + timedelta(
            hours=SLA_HOURS[priority]
        )

        ticket = Ticket(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status="Open",
            user_id=current_user.id,
            created_at=created_time,
            sla_deadline=sla_deadline
        )

        db.session.add(ticket)
        db.session.commit()

        flash("Ticket created successfully!", "success")

        return redirect(url_for("my_tickets"))

    return render_template("create_ticket.html")


# MY TICKETS
@app.route("/my-tickets")
@login_required
def my_tickets():

    tickets = Ticket.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    return render_template(
        "my_tickets.html",
        tickets=tickets,
        now=datetime.utcnow()
    )


# UPDATE TICKET
@app.route("/update-ticket/<int:ticket_id>", methods=["POST"])
@staff_required
def update_ticket(ticket_id):

    ticket = Ticket.query.get_or_404(ticket_id)

    new_status = request.form.get("status")
    assigned_to_id = request.form.get("assigned_to")

    if new_status in ["Open", "In Progress", "Resolved"]:

        ticket.status = new_status

        if new_status == "Resolved":
            ticket.resolved_at = datetime.utcnow()
        else:
            ticket.resolved_at = None

    if assigned_to_id:

        try:
            staff_id = int(assigned_to_id)

            staff_member = User.query.filter_by(
                id=staff_id,
                role="staff"
            ).first()

            if staff_member:
                ticket.assigned_to_id = staff_member.id

        except ValueError:
            pass

    else:
        ticket.assigned_to_id = None

    db.session.commit()

    flash("Ticket updated successfully!", "success")

    return redirect(url_for("staff_dashboard"))


# LOGOUT
@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# RUN APPLICATION
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )