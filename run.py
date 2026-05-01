from flask import render_template, session, request, url_for, redirect, flash
from pathlib import Path
import re, smtplib, cv2
from email.mime.text import MIMEText
import numpy as np
from app import app, db, totp
from app.models import Aadhaar, Entitlement
from face_utils import decode_base64_image, compare_faces,is_face_visible

# ---------------- Usage Model ----------------
class Usage(db.Model):
    __tablename__ = "ration_usage"

    id = db.Column(db.Integer, primary_key=True)
    aadhaarNo = db.Column(db.String(12), db.ForeignKey("aadhaar.aadhaarNo"))
    rice = db.Column(db.Integer, default=0)
    wheat = db.Column(db.Integer, default=0)
    coarse = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# ---------------- Config ----------------
PHOTO_DIR = Path("data/faces")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

def send_email(to_email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "OTP Verification"
    msg["From"] = "yourgmail@gmail.com"
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("yourgmail@gmail.com", "your_app_password")
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

# ---------------- Aadhaar Validation ----------------
# Verhoeff tables
_D = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]

_P = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]

def compare_faces(stored_bytes, new_img):
    stored_img = cv2.imdecode(np.frombuffer(stored_bytes, np.uint8), cv2.IMREAD_COLOR)

    # resize for consistency
    stored_img = cv2.resize(stored_img, (200, 200))
    new_img = cv2.resize(new_img, (200, 200))

    diff = np.mean((stored_img - new_img) ** 2)

    # threshold (tune this)
    return diff < 2000, diff

def is_valid_aadhaar(num: str) -> bool:
    # Step 1: Clean input
    num = re.sub(r"\D", "", num)

    # Step 2: Must be 12 digits
    if not re.fullmatch(r"\d{12}", num):
        return False

    # Step 3: Verhoeff checksum validation
    c = 0
    for i, digit in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(digit)]]

    return c == 0

# ---------------- Helpers ----------------
def set_current_user(aadhaar_no):
    user = db.session.get(Aadhaar, aadhaar_no)
    if not user:
        return False
    session["currentUser"] = user.aadhaarNo
    return True

def compute_max_amount(entitlement):
    if entitlement and getattr(entitlement, "maxAmount", None):
        return int(entitlement.maxAmount)
    return 10

# ---------------- Routes ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        aadhaar_no = request.form.get("aadhaarNo")
        face_data = request.form.get("face_image")

        # 🔒 Validate Aadhaar
        if not is_valid_aadhaar(aadhaar_no):
            return render_template("login.html", error="Invalid Aadhaar")

        user = db.session.get(Aadhaar, aadhaar_no)

        # ❌ User not found
        if not user:
            return redirect(url_for("register", aadhaarNo=aadhaar_no))

        # ❌ No face captured
        if not face_data:
            return render_template("login.html", error="Please capture face")

        # 🔄 Decode image
        img = decode_base64_image(face_data)

        # 🔍 Compare faces
        match, score = compare_faces(user.face_image, img)

        if not match:
            return render_template(
                "login.html",
                error=f"Face mismatch ❌ (score: {score:.4f})"
            )

        # ✅ SUCCESS LOGIN
        session["currentUser"] = user.aadhaarNo

        flash("Login successful", "success")

        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/face_login", methods=["GET", "POST"])
def face_login():
    if request.method == "POST":
        aadhaar = request.form.get("aadhaarNo")
        user = db.session.get(Aadhaar, aadhaar)

        if not user or not user.face_image:
            flash("No face registered", "danger")
            return redirect(url_for("face_login"))

        face_data = request.form.get("face_image")
        if not face_data:
            flash("Capture face first", "danger")
            return redirect(url_for("face_login"))

        img = decode_base64_image(face_data)
        match, score = compare_faces(user.face_image, img)

        if match:
            set_current_user(aadhaar)
            flash("Face login success", "success")
            return redirect(url_for("index"))
        else:
            flash("Face not matched", "danger")
            return redirect(url_for("face_login"))

    return render_template("face_login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    # ✅ Always take Aadhaar from URL first, fallback to form
    aadhaar_no = request.args.get("aadhaarNo") or request.form.get("aadhaarNo")

    # 🔒 Block direct access without Aadhaar
    if not aadhaar_no:
        return redirect(url_for("login"))

    if request.method == "POST":

        # 🔥 NEVER trust form Aadhaar blindly
        form_aadhaar = request.form.get("aadhaarNo")

        if form_aadhaar != aadhaar_no:
            return "Invalid Aadhaar tampering detected", 400

        # ✅ Check if already registered
        existing = db.session.get(Aadhaar, aadhaar_no)
        if existing:
            return redirect(url_for("login"))

        # ---------------------------
        # Extract form data
        # ---------------------------
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        mobile = request.form.get("mobileNo", "").strip()
        category = request.form.get("category", "").strip()
        face_data = request.form.get("face_image")

        # ---------------------------
        # Validations
        # ---------------------------
        if not name or len(name) < 2:
            return render_template("register.html",
                                   aadhaarNo=aadhaar_no,
                                   error="Invalid name")

        if not mobile.isdigit() or len(mobile) != 10:
            return render_template("register.html",
                                   aadhaarNo=aadhaar_no,
                                   error="Invalid mobile number")

        if not face_data:
            return render_template("register.html",
                                   aadhaarNo=aadhaar_no,
                                   error="Face capture required")

        # ---------------------------
        # Decode + validate face
        # ---------------------------
        img = decode_base64_image(face_data)

        if img is None:
            return render_template("register.html",
                                   aadhaarNo=aadhaar_no,
                                   error="Invalid image")

        if not is_face_visible(img):
            return render_template("register.html",
                                   aadhaarNo=aadhaar_no,
                                   error="Face not clearly visible. Please retry.")

        # Convert to bytes
        _, buf = cv2.imencode(".jpg", img)
        face_bytes = buf.tobytes()

        # ---------------------------
        # Save user
        # ---------------------------
        user = Aadhaar(
            aadhaarNo=aadhaar_no,
            name=name,
            address=address,
            mobileNo=mobile,
            category=category,
            face_image=face_bytes
        )

        db.session.add(user)
        db.session.commit()

        # ✅ Optional: flash message
        flash("Registration successful. Please login.", "success")

        return redirect(url_for("login"))

    # ---------------------------
    # GET request
    # ---------------------------
    return render_template("register.html", aadhaarNo=aadhaar_no)

@app.route("/")
def index():
    cur_id = session.get("currentUser")

    if not cur_id:
        return redirect(url_for("login"))

    user = db.session.get(Aadhaar, cur_id)

    if not user:
        return render_template("not_found.html"), 404

    entitlement = Entitlement.query.filter_by(category=user.category).first()

    # ✅ Get all usage
    usages = Usage.query.filter_by(aadhaarNo=cur_id).all()

    # ✅ Calculate totals
    total_rice = sum(u.rice for u in usages)
    total_wheat = sum(u.wheat for u in usages)
    total_coarse = sum(u.coarse for u in usages)

    total_used = total_rice + total_wheat + total_coarse
    max_allowed = entitlement.maxAmount if entitlement else 10
    remaining = max_allowed - total_used

    return render_template(
        "user_ration.html",
        user=user,
        entitlement=entitlement,
        total_used=total_used,
        remaining=remaining,
        usages=usages[-5:]  # last 5 records
    )

@app.route("/sendOtp")
def sendOtp():
    cur = session.get("currentUser")
    if not cur:
        return redirect(url_for("login"))

    user = db.session.get(Aadhaar, cur)

    otp = totp.now()
    session["OTP"] = otp

    if user.email:
        send_email(user.email, otp)

    return redirect(url_for("stock"))


@app.route("/verifyOtp/<otp>")
def verifyOtp(otp):
    if totp.verify(otp) or session.get("OTP") == otp:
        return "True"
    return "False"


@app.route("/stock", methods=["GET", "POST"])
def stock():
    cur = session.get("currentUser")
    if not cur:
        return redirect(url_for("login"))

    max_allowed = session.get("maxAmount", 10)

    if request.method == "POST":
        if request.form.get("otp_verified") != "1":
            flash("Verify OTP first", "danger")
            return redirect(url_for("stock"))

        rice = int(request.form.get("riceQuantity", 0))
        wheat = int(request.form.get("wheatQuantity", 0))
        coarse = int(request.form.get("coarseQuantity", 0))

        total = rice + wheat + coarse

        if total > max_allowed:
            flash("Limit exceeded", "danger")
            return redirect(url_for("stock"))

        usage = Usage(aadhaarNo=cur, rice=rice, wheat=wheat, coarse=coarse)
        db.session.add(usage)
        db.session.commit()

        flash("Order placed", "success")
        return redirect(url_for("index"))

    return render_template("stock.html", maxAllowed=max_allowed)

@app.route("/getUsage")
def getUsage():
    cur_id = session.get("currentUser")

    # 🔒 Not logged in
    if not cur_id:
        return redirect(url_for("login"))

    # ✅ Get user
    user = db.session.get(Aadhaar, cur_id)
    if not user:
        return render_template("not_found.html"), 404

    # ✅ Get usage records (latest first)
    usages = Usage.query.filter_by(aadhaarNo=cur_id)\
                        .order_by(Usage.created_at.desc())\
                        .all()

    # ✅ Calculate totals
    total_rice = sum(u.rice for u in usages)
    total_wheat = sum(u.wheat for u in usages)
    total_coarse = sum(u.coarse for u in usages)

    total_used = total_rice + total_wheat + total_coarse

    # ✅ Monthly usage (important for analytics)
    from datetime import datetime
    current_month = datetime.now().month

    monthly_usage = [
        u for u in usages if u.created_at and u.created_at.month == current_month
    ]

    monthly_total = sum(
        u.rice + u.wheat + u.coarse for u in monthly_usage
    )

    return render_template(
        "getUsage.html",
        user=user,
        usages=usages,
        total_used=total_used,
        monthly_total=monthly_total,
        total_rice=total_rice,
        total_wheat=total_wheat,
        total_coarse=total_coarse
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():
    cur = session.get("currentUser")

    if not cur:
        return redirect(url_for("login"))

    user = db.session.get(Aadhaar, cur)

    if request.method == "POST":
        user.name = request.form.get("name")
        user.address = request.form.get("address")
        user.mobileNo = request.form.get("mobileNo")

        db.session.commit()

        flash("Profile updated successfully", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)

@app.route("/logout")
def logout():
    # 🔥 Clear everything related to user
    session.clear()

    # Optional message
    flash("Logged out successfully", "info")

    return redirect(url_for("login"))

@app.route("/check_face", methods=["POST"])
def check_face():
    data = request.json.get("image")

    img = decode_base64_image(data)

    if not is_face_visible(img):
        return {"ok": False, "msg": "Face not clearly visible. Please retry."}

    return {"ok": True}

@app.route("/check_user/<aadhaar>")
def check_user(aadhaar):

    # 🔒 Step 1: Validate Aadhaar format
    if not is_valid_aadhaar(aadhaar):
        return {"valid": False, "exists": False}

    # 🔍 Step 2: Check DB
    user = db.session.get(Aadhaar, aadhaar)

    return {
        "valid": True,
        "exists": bool(user)
    }
# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)