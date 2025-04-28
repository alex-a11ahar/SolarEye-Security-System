import cv2
import os
import firebase_admin
from firebase_admin import credentials, storage
from datetime import datetime

# Firebase configuration
BUCKET_NAME = "gs://solareye-security-system.firebasestorage.app"
CREDENTIALS_PATH = "path/to/your-firebase-adminsdk.json"

# Initialize Firebase Admin SDK if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_NAME})

bucket = storage.bucket()

# Define video capture settings
VIDEO_FILENAME = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
LOCAL_VIDEO_PATH = f"./{VIDEO_FILENAME}"
VIDEO_DURATION = 10  # seconds
FPS = 20
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Start capturing video
cap = cv2.VideoCapture(0)
counter = 0
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(LOCAL_VIDEO_PATH, fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))

print("Recording video...")
while counter < VIDEO_DURATION * FPS:
    ret, frame = cap.read()
    if not ret:
        break
    out.write(frame)
    counter += 1

cap.release()
out.release()
cv2.destroyAllWindows()

print(f"Video saved locally: {LOCAL_VIDEO_PATH}")

# Upload to Firebase Storage
blob = bucket.blob(f"videos/{VIDEO_FILENAME}")
blob.upload_from_filename(LOCAL_VIDEO_PATH)
blob.make_public()

print(f"Video uploaded to Firebase: {blob.public_url}")

# Optional: Remove local file after upload
os.remove(LOCAL_VIDEO_PATH)
print("Local file deleted.")
