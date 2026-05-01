from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
import pymysql
import pyotp

# Use PyMySQL as the MySQLdb driver
pymysql.install_as_MySQLdb()

# Example TOTP secret (don’t hardcode in production)
totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")

app = Flask(__name__)
app.config['SECRET_KEY'] = "sarvesh"

# ✅ XAMPP default settings
# - user: root
# - password: "" (empty, unless you set one in phpMyAdmin)
# - host: 127.0.0.1
# - port: 3306
# - database: dvwa   (replace with your DB name)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@127.0.0.1:3306/dvwa'

# If you set a password for root (example: 'sarvesh'):
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:sarvesh@127.0.0.1:3306/dvwa'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Optional: keep connections healthy
# app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}