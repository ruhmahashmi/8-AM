from flask import Flask, render_template

app = Flask(__name__)

# Route for the homepage or another page
@app.route('/')
def signup():
    return render_template('sign-up.html')  # This renders signup.html

# Route for the login page
@app.route('/login')
def login():
    return render_template('login.html')  # This renders login.html from the templates folder

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')  # This renders dashboard.html from the templates folder

@app.route('/profile')
def profile():
    return render_template('profile.html')  # This renders profile.html from the templates folder
if __name__ == '__main__':
    app.run(debug=True)  # Run the app in debug mode for easier troubleshooting
