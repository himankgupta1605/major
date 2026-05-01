from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import pyotp

db = SQLAlchemy()   # ❗ create db WITHOUT app

totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "sarvesh"

    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://root:ORZJQlwukQOcReuYDEQaADoqCwBge4r1@dpg-d7q7uphkh4rs73b3935g-a/major_dbqa"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # ✅ import models AFTER db is ready
    from app import models

    with app.app_context():
        db.create_all()

    return app