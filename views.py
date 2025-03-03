from flask import Blueprint, render_template
from flask_login import login_required, current_user

views = Blueprint('views', __name__)

@views.route('/')
@login_required
def home():
    return render_template("dashboard.html", userName=current_user.firstName, user=current_user)

@views.route('/profile')
@login_required
def profile():
    return render_template("profile.html", user=current_user)

@views.route('/schedule')
@login_required
def schedule():
    return render_template("schedule.html", user=current_user)