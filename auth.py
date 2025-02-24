from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, current_user
from . import db
from .data import User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            if user.password == password:
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='error')
                
        else:
            flash('Email does not exist.', category='error')
    return render_template("login.html", user=current_user)

@auth.route('/sign-up', methods = ['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        firstName = request.form.get('firstName')
        lastName = request.form.get('lastName')
        year = request.form.get('year')
        major = request.form.get('major')
        minor = request.form.get('minor')
        co_op = request.form.get('co-op')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user  = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        elif len(email) < 4:
            flash("Email must be greater than 4 characters.", category='error')
            
        elif len(firstName) < 2:
            flash("First name must be greater than 2 characters.", category='error')
        elif len(lastName) < 2:
            flash("Last name must be greater than 2 characters.", category='error')
        elif password1 != password2:
            flash("Passwords don't match.", category='error')
            
        elif len(password1) < 7:
            flash("Password must be at least 7 characters.", category='error')
            
        else:
            new_user = User(email=email, firstName=firstName, lastName=lastName, year=year, co_op= co_op, major=major, minor=minor, password=password1)
            db.session.add(new_user)
            db.session.commit()
            login_user
            flash('Account created!', category='success')
            return redirect(url_for('views.home'))

    return render_template("sign_up.html", user=current_user)