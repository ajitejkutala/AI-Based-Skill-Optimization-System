from __future__ import annotations

import os
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for, session

from models import Employee, JobRole, db, ensure_sqlite_schema
from services import extract_skills, rank_employees, recommend_learning

load_dotenv()


import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def _instance_sqlite_uri(app: Flask) -> str:
    """Create/return an SQLite path inside Flask `instance/` folder, or system temp on Vercel."""
    if os.environ.get("VERCEL"):
        db_path = os.path.join(tempfile.gettempdir(), "workforce_skill_opt.db")
        return "sqlite:///" + db_path.replace("\\", "/")
    os.makedirs(app.instance_path, exist_ok=True)
    return "sqlite:///" + os.path.join(app.instance_path, "workforce_skill_opt.db")


def create_app() -> Flask:
    """
    Create and configure the Flask app.
    - DB tables are created automatically on first run
    """
    app = Flask(__name__, template_folder=TEMPLATES_DIR, instance_relative_config=True)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # Database config
    db_uri = os.environ.get("DATABASE_URL")
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri or _instance_sqlite_uri(app)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Sentence embedding model (SentenceTransformers)
    app.config["EMBEDDING_MODEL_NAME"] = os.environ.get(
        "EMBEDDING_MODEL_NAME",
        "all-MiniLM-L6-v2",
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_sqlite_schema()

    def get_current_job() -> JobRole | None:
        """Return latest saved job description."""
        return JobRole.query.order_by(JobRole.created_at.desc()).first()

    def get_employee_dicts() -> list[dict]:
        employees = Employee.query.order_by(Employee.updated_at.desc()).all()

        return [
            {
                "id": e.id,
                "full_name": e.full_name,
                "title": e.title or "",
                "resume_text": e.resume_text or "",
                "skills": e.skills_list(),
            }
            for e in employees
        ]

    def get_job_dict(job: JobRole) -> dict:
        return {
            "role_name": job.role_name,
            "description": job.description or "",
            "required_skills": job.required_skills_list(),
        }

    # -----------------------------
    # Create Employee
    # -----------------------------
    @app.route("/employees", methods=["GET", "POST"])
    def employee_create():
        if request.method == "GET":
            return redirect(url_for("dashboard"))

        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower() or None
        password = (request.form.get("password") or "").strip()
        title = (request.form.get("title") or "").strip() or None
        department = (request.form.get("department") or "").strip() or None
        years_experience_raw = (request.form.get("years_experience") or "").strip()
        resume_text = (request.form.get("resume_text") or "").strip() or None
        skills_manual = (request.form.get("skills_manual") or "").strip()

        if not full_name:
            flash("Full name is required.", "error")
            return redirect(url_for("dashboard"))

        years_experience = None
        if years_experience_raw:
            try:
                years_experience = int(years_experience_raw)
            except Exception:
                years_experience = None

        extracted = extract_skills(resume_text or "")
        manual = [s.strip().lower() for s in skills_manual.split(",") if s.strip()]

        skills = sorted(set(extracted) | set(manual))

        existing = Employee.query.filter_by(email=email).first() if email else None
        if existing:
            existing.full_name = full_name
            if title:
                existing.title = title
            if department:
                existing.department = department
            if years_experience is not None:
                existing.years_experience = years_experience
            if resume_text:
                existing.resume_text = resume_text
            existing.set_skills(skills)
            if password:
                existing.set_password(password)
            try:
                db.session.commit()
                flash("Employee saved.", "success")
            except Exception:
                db.session.rollback()
                flash("Could not save employee.", "error")
            return redirect(url_for("dashboard"))

        e = Employee(
            full_name=full_name,
            email=email,
            title=title,
            department=department,
            years_experience=years_experience,
            resume_text=resume_text,
            skills_json=None,
        )

        e.set_skills(skills)
        if password:
            e.set_password(password)

        db.session.add(e)

        try:
            db.session.commit()
            flash("Employee saved.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not save employee.", "error")

        return redirect(url_for("dashboard"))

    # -----------------------------
    # Dashboard
    # -----------------------------
    @app.route("/", methods=["GET", "POST"])
    def dashboard():
        if request.method == "POST":
            # If form was submitted with employee fields
            if request.form.get("full_name"):
                return employee_create()
            # If form was submitted with job role fields
            if request.form.get("role_name"):
                return job_save()

        employees = Employee.query.order_by(Employee.updated_at.desc()).all()
        job = get_current_job()

        return render_template(
            "dashboard.html",
            title="Dashboard",
            employees=employees,
            job=job,
            active="dashboard",
        )

    # -----------------------------
    # Edit Employee
    # -----------------------------
    @app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
    def employee_edit(employee_id: int):

        e = Employee.query.get_or_404(employee_id)

        if request.method == "POST":
            e.full_name = (request.form.get("full_name") or "").strip() or e.full_name
            email = (request.form.get("email") or "").strip().lower()
            if email:
                e.email = email
            title = (request.form.get("title") or "").strip()
            if title:
                e.title = title
            dept = (request.form.get("department") or "").strip()
            if dept:
                e.department = dept
            resume = (request.form.get("resume_text") or "").strip()
            if resume:
                e.resume_text = resume

            years_raw = (request.form.get("years_experience") or "").strip()
            skills_manual = (request.form.get("skills_manual") or "").strip()
            new_password = (request.form.get("new_password") or "").strip()

            try:
                e.years_experience = int(years_raw) if years_raw else None
            except Exception:
                e.years_experience = None

            extracted = extract_skills(e.resume_text or "")
            manual = [s.strip().lower() for s in skills_manual.split(",") if s.strip()]

            skills = sorted(set(extracted) | set(manual))
            e.set_skills(skills)

            if new_password:
                e.set_password(new_password)

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Could not update employee.", "error")
                return redirect(url_for("talent_pool"))

            flash("Employee updated.", "success")
            return redirect(url_for("talent_pool"))

        return render_template(
            "employee_edit.html",
            title="Update employee",
            e=e,
            active="talent",
        )

    # -----------------------------
    # -----------------------------
    # Save Job Role
    # -----------------------------
    @app.route("/job", methods=["GET", "POST"])
    def job_save():
        if request.method == "GET":
            return redirect(url_for("dashboard"))

        role_name = (request.form.get("role_name") or "").strip()
        department = (request.form.get("department") or "").strip() or None
        description = (request.form.get("description") or "").strip() or None
        required_skills = (request.form.get("required_skills") or "").strip()

        if not role_name:
            flash("Job title is required.", "error")
            return redirect(url_for("dashboard"))

        job = JobRole(
            role_name=role_name,
            department=department,
            description=description,
            required_skills_json=None,
        )

        job.set_required_skills(
            [s.strip().lower() for s in required_skills.split(",") if s.strip()]
        )

        db.session.add(job)

        try:
            db.session.commit()
            flash("Job saved.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not save job.", "error")

        return redirect(url_for("dashboard"))

    # -----------------------------
    # Talent Pool
    # -----------------------------
    @app.get("/talent")
    def talent_pool():

        employees = Employee.query.order_by(Employee.updated_at.desc()).all()

        return render_template(
            "talent.html",
            title="Talent Pool",
            employees=employees,
            active="talent",
        )

    # -----------------------------
    # Delete Employee
    # -----------------------------
    @app.route("/employees/<int:employee_id>/delete", methods=["GET", "POST"])
    def employee_delete(employee_id: int):
        if request.method == "GET":
            return redirect(url_for("talent_pool"))

        e = Employee.query.get_or_404(employee_id)

        db.session.delete(e)

        try:
            db.session.commit()
            flash("Employee deleted.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not delete employee.", "error")

        return redirect(url_for("talent_pool"))

    # -----------------------------
    # Role Matching
    # -----------------------------
    @app.get("/role")
    def role_matching():

        all_jobs = JobRole.query.order_by(JobRole.created_at.desc()).all()
        job_id = request.args.get("job_id", type=int)
        job = None
        if job_id is not None:
            job = next((j for j in all_jobs if j.id == job_id), None)
        if job is None:
            job = all_jobs[0] if all_jobs else None

        employees = Employee.query.order_by(Employee.updated_at.desc()).all()

        ranked = []
        recs = {}
        required = []

        if job:
            required = job.required_skills_list()

            ranked = rank_employees(
                model_name=app.config["EMBEDDING_MODEL_NAME"],
                employees=get_employee_dicts(),
                job=get_job_dict(job),
            )

            recs = {
                r.employee_id: recommend_learning(r.missing_skills)
                for r in ranked
            }

        employees_map = {e.id: e for e in employees}

        return render_template(
            "role_match.html",
            title="Role Matching",
            job=job,
            jobs=all_jobs,
            ranked=ranked,
            recs=recs,
            required_skills=required,
            employees_map=employees_map,
            active="role",
        )

    # -----------------------------
    # Employee self-service portal
    # -----------------------------
    @app.route("/employee/login", methods=["GET", "POST"])
    def employee_login():

        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = (request.form.get("password") or "").strip()

            emp = None
            if email and password:
                emp = Employee.query.filter_by(email=email).first()
                if not emp or not emp.check_password(password):
                    emp = None

            if not emp:
                flash("Invalid email or password.", "error")
                return redirect(url_for("employee_login"))

            session["employee_id"] = emp.id
            flash("Logged in successfully.", "success")
            return redirect(url_for("employee_portal"))

        return render_template(
            "employee_login.html",
            title="Staff login",
            active="employee_portal",
        )

    @app.get("/employee/logout")
    def employee_logout():
        session.pop("employee_id", None)
        flash("You have been logged out.", "success")
        return redirect(url_for("employee_login"))

    @app.route("/employee/portal", methods=["GET", "POST"])
    def employee_portal():

        emp_id = session.get("employee_id")
        if not emp_id:
            flash("Please log in to access your portal.", "error")
            return redirect(url_for("employee_login"))

        e = Employee.query.get_or_404(emp_id)

        if request.method == "POST":
            e.full_name = (request.form.get("full_name") or "").strip() or e.full_name
            email = (request.form.get("email") or "").strip().lower()
            if email:
                e.email = email
            title = (request.form.get("title") or "").strip()
            if title:
                e.title = title
            dept = (request.form.get("department") or "").strip()
            if dept:
                e.department = dept
            resume = (request.form.get("resume_text") or "").strip()
            if resume:
                e.resume_text = resume

            years_raw = (request.form.get("years_experience") or "").strip()
            skills_manual = (request.form.get("skills_manual") or "").strip()
            new_password = (request.form.get("new_password") or "").strip()

            try:
                e.years_experience = int(years_raw) if years_raw else None
            except Exception:
                e.years_experience = None

            extracted = extract_skills(e.resume_text or "")
            manual = [s.strip().lower() for s in skills_manual.split(",") if s.strip()]
            skills = sorted(set(extracted) | set(manual))
            e.set_skills(skills)

            if new_password:
                e.set_password(new_password)

            try:
                db.session.commit()
                flash("Profile updated.", "success")
            except Exception:
                db.session.rollback()
                flash("Could not update your profile.", "error")

            return redirect(url_for("employee_portal"))

        # Performance view vs current job
        job = get_current_job()
        match = None
        recs = []
        required_skills: list[str] = []

        if job:
            required_skills = job.required_skills_list()
            emp_dict = {
                "id": e.id,
                "full_name": e.full_name,
                "title": e.title or "",
                "resume_text": e.resume_text or "",
                "skills": e.skills_list(),
            }
            results = rank_employees(
                model_name=app.config["EMBEDDING_MODEL_NAME"],
                employees=[emp_dict],
                job=get_job_dict(job),
            )
            if results:
                match = results[0]
                recs = recommend_learning(match.missing_skills)

        return render_template(
            "employee_portal.html",
            title="My profile",
            e=e,
            job=job,
            match=match,
            recs=recs,
            required_skills=required_skills,
            active="employee_portal",
        )

    @app.get("/health")
    def health():
        """Plain health check for load balancers and hosting dashboards."""
        return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(404)
    def page_not_found(_e):
        return render_template("errors/404.html", title="Page not found", active=""), 404

    @app.route("/dashboard", methods=["GET", "POST"])
    def dashboard_alias():
        return dashboard()

    @app.route("/match", methods=["GET", "POST"])
    def match_alias():
        return redirect(url_for("role_matching"))

    @app.route("/api/index", methods=["GET", "POST"])
    @app.route("/api", methods=["GET", "POST"])
    def vercel_index_alias():
        return dashboard()

    return app


class VercelPathMiddleware:
    """
    Transparent WSGI middleware for Vercel serverless functions.
    Ensures that rewritten URLs (e.g. /role, /talent, /employees, /job)
    preserve their original PATH_INFO and HTTP methods.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        if path_info in ("/api/index", "/api", "/api/index.py", ""):
            # 1. Check query parameter __vercel_route
            query_string = environ.get("QUERY_STRING", "")
            if "__vercel_route" in query_string:
                import urllib.parse
                params = urllib.parse.parse_qsl(query_string)
                route_val = None
                remaining = []
                for k, v in params:
                    if k == "__vercel_route":
                        route_val = v
                    else:
                        remaining.append((k, v))
                if route_val:
                    clean = "/" + route_val.lstrip("/")
                    environ["PATH_INFO"] = clean
                    environ["QUERY_STRING"] = urllib.parse.urlencode(remaining)

            # 2. Check proxy headers
            if environ.get("PATH_INFO") in ("/api/index", "/api", "/api/index.py", ""):
                for header in ("HTTP_X_FORWARDED_URI", "HTTP_X_MATCHED_PATH", "HTTP_X_NOW_ROUTE_MATCHES"):
                    orig = environ.get(header)
                    if orig and orig not in ("/api/index", "/api", "/api/index.py"):
                        parts = orig.split("?", 1)
                        environ["PATH_INFO"] = "/" + parts[0].lstrip("/")
                        if len(parts) > 1 and not environ.get("QUERY_STRING"):
                            environ["QUERY_STRING"] = parts[1]
                        break

            # 3. Fallback to / if still on entrypoint
            if environ.get("PATH_INFO") in ("/api/index", "/api", "/api/index.py", ""):
                environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# WSGI entrypoint for production servers (e.g. gunicorn "main:app", Vercel "@vercel/python")
app = create_app()
app.wsgi_app = VercelPathMiddleware(app.wsgi_app)


if __name__ == "__main__":
    # Local development server
    app.run(
        debug=True,
        host=os.environ.get("FLASK_RUN_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )