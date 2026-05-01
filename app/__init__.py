from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
import pyotp
from app.models import Aadhaar


# TOTP
totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")

app = Flask(__name__)
app.config['SECRET_KEY'] = "sarvesh"

# ✅ PostgreSQL connection (Render)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://root:ORZJQlwukQOcReuYDEQaADoqCwBge4r1@dpg-d7q7uphkh4rs73b3935g-a/major_dbqa"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
with app.app_context():
    db.create_all()