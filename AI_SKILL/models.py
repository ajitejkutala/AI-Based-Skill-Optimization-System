"""
Database models (SQLAlchemy).

Kept intentionally small:
- Employee: stores profile text + normalized skills list
- JobRole: stores the current job title/description + required skills list
"""

from __future__ import annotations

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


class Employee(db.Model):  # type: ignore[misc]
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=True, unique=True)
    title = db.Column(db.String(200), nullable=True)
    department = db.Column(db.String(200), nullable=True)
    years_experience = db.Column(db.Integer, nullable=True)
    resume_text = db.Column(db.Text, nullable=True)
    # Skills with levels (JSON string): {"python": 85, "sql": 70}
    skills_json = db.Column(db.Text, nullable=True)
    skills_csv = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def skills_list(self) -> list[str]:
        if not self.skills_csv:
            return []
        return [s.strip() for s in self.skills_csv.split(",") if s.strip()]

    def set_skills(self, skills: list[str]) -> None:
        normalized = sorted({s.strip().lower() for s in skills if s and s.strip()})
        self.skills_csv = ", ".join(normalized)

    # Auth helpers
    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash

        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class JobRole(db.Model):  # type: ignore[misc]
    __tablename__ = "job_roles"

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    # Required skills with thresholds (JSON string): {"python": 80, "tensorflow": 75}
    required_skills_json = db.Column(db.Text, nullable=True)
    required_skills_csv = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def required_skills_list(self) -> list[str]:
        if not self.required_skills_csv:
            return []
        return [s.strip() for s in self.required_skills_csv.split(",") if s.strip()]

    def set_required_skills(self, skills: list[str]) -> None:
        normalized = sorted({s.strip().lower() for s in skills if s and s.strip()})
        self.required_skills_csv = ", ".join(normalized)


def ensure_sqlite_schema() -> None:
    """
    Lightweight SQLite auto-migration.
    Safely adds missing nullable columns if SQLite is in use.
    Skipped automatically on other database engines (e.g. PostgreSQL, MySQL).
    """
    try:
        if db.engine.dialect.name != "sqlite":
            return
        with db.engine.begin() as conn:
            # employees table
            emp_cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(employees)")).fetchall()
            }
            for col, ddl in [
                ("department", "ALTER TABLE employees ADD COLUMN department VARCHAR(200)"),
                ("years_experience", "ALTER TABLE employees ADD COLUMN years_experience INTEGER"),
                ("skills_json", "ALTER TABLE employees ADD COLUMN skills_json TEXT"),
                ("password_hash", "ALTER TABLE employees ADD COLUMN password_hash VARCHAR(255)"),
            ]:
                if col not in emp_cols:
                    conn.execute(text(ddl))

            # job_roles table
            role_cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(job_roles)")).fetchall()
            }
            for col, ddl in [
                ("department", "ALTER TABLE job_roles ADD COLUMN department VARCHAR(200)"),
                ("required_skills_json", "ALTER TABLE job_roles ADD COLUMN required_skills_json TEXT"),
            ]:
                if col not in role_cols:
                    conn.execute(text(ddl))
    except Exception as exc:
        print(f"[models] Schema check warning: {exc}")

