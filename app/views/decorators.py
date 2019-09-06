
"""
decorators.py - Decorators for applied to routes/views
"""
from flask import flash, redirect, session, url_for
from functools import wraps

LOGIN_FUNCTION = "login.do_login"


# Decorator to check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized - Please Log In", "danger")
            return redirect(url_for(LOGIN_FUNCTION))
    return wrap


# Decorator to check if user is an administrator
def is_admin_user(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session['is_admin']:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized - Please Log In As An Administrator", "danger")
            return redirect(url_for(LOGIN_FUNCTION))
    return wrap


# Decorator to check if we have an active case set on our session
def is_case_set(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'case' in session:
            return f(*args, **kwargs)
        else:
            flash("Select a case if you want to add, remove, or view case items.", "primary")
            return redirect(url_for("case_routes.list_cases"))
    return wrap
