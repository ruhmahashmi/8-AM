from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from os import path

app = Flask(__name__)

DB_NAME = 'users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}' 
app.config['SECRET_KEY'] = 'your_secret_key' 

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def signup():
    return render_template('sign-up.html')  # This renders sign-up.html

# Route to handle sign-up form submission
@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if the username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('signup'))

        # Create a new user
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html') 

@app.route('/login', methods=['POST'])
def login_post():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the user exists
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            flash('Login successful!', 'success')
            return render_template('/dashboard')
        else:
            flash('Invalid username or password!', 'error')
            return render_template('/login')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')  

@app.route('/profile')
def profile():
    return render_template('profile.html')  

if __name__ == '__main__':
    app.run(debug=True) 

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')