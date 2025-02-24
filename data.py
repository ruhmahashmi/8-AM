from . import db
from flask_login import UserMixin
from sqlalchemy import func

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    firstName = db.Column(db.String(150))
    lastName = db.Column(db.String(150))
    year = db.Column(db.Integer)
    major = db.Column(db.String(150))
    minor = db.Column(db.String(150))
    co_op = db.Column(db.String(150))