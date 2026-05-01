import cv2
import base64
import numpy as np

# ---------------------------
# Load Haar Cascade (once)
# ---------------------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

if face_cascade.empty():
    raise RuntimeError("❌ Haar cascade not loaded. Check OpenCV installation.")

# ---------------------------
# Decode Base64 Image
# ---------------------------
def decode_base64_image(data_uri):
    try:
        encoded = data_uri.split(",")[1]
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print("Decode error:", e)
        return None


# ---------------------------
# Detect & Extract Face
# ---------------------------
def extract_face(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,
        minNeighbors=3,
        minSize=(60, 60)
    )

    if len(faces) == 0:
        return None

    # 🔥 Take largest face (important)
    faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
    x, y, w, h = faces[0]

    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (100, 100))

    return face


# ---------------------------
# Check Face Visibility
# ---------------------------
def is_face_visible(img):
    if img is None:
        return False

    face = extract_face(img)
    return face is not None


# ---------------------------
# Compare Faces (Improved)
# ---------------------------
def compare_faces(stored_bytes, new_img, threshold=0.03):
    """
    Compare stored face with new face.
    Returns (match: bool, score: float)
    """

    try:
        # Decode stored image
        stored_arr = np.frombuffer(stored_bytes, np.uint8)
        stored_img = cv2.imdecode(stored_arr, cv2.IMREAD_COLOR)

        # Extract faces
        face1 = extract_face(stored_img)
        face2 = extract_face(new_img)

        if face1 is None or face2 is None:
            return False, 999.0

        # Normalize
        face1 = face1 / 255.0
        face2 = face2 / 255.0

        # 🔥 MSE difference
        mse = np.mean((face1 - face2) ** 2)

        return mse < threshold, float(mse)

    except Exception as e:
        print("Face compare error:", e)
        return False, 999.0