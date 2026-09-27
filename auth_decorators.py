"""
auth_decorators.py
------------------
Centralised authentication and role-based access control (RBAC) decorators.

Usage:
    from auth_decorators import admin_required, student_required, company_required

    @admin_bp.route("/dashboard")
    @admin_required
    def dashboard():
        ...
"""

from functools import wraps
from flask import session, redirect, url_for, flash


def admin_required(f):
    """Protect an admin route. Redirects to React login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_user" not in session:
            flash("Please log in to access the admin portal.", "warning")
            return redirect("/")  # Redirect to React login app
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """Protect a student route. Redirects to React login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "student_reg_no" not in session:
            flash("Please log in to access your student dashboard.", "warning")
            return redirect("/")  # Redirect to React login app
        return f(*args, **kwargs)
    return decorated


def company_required(f):
    """Protect a company HR route. Redirects to React login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "company_email" not in session:
            flash("Please log in to access the company portal.", "warning")
            return redirect("/")  # Redirect to React login app
        return f(*args, **kwargs)
    return decorated
