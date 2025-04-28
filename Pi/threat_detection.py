import subprocess
import os
import threading
from flask import Flask, send_from_directory, render_template_string
import logging
import socket
import cv2
import time
import firebase_admin
from firebase_admin import credentials, db

# Suppress Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Initialize Flask app
app = Flask(__name__)

# Firebase Initialization
cred = credentials.Certificate("firebase_credentials.json")  # Update with your Firebase credentials JSON file
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://gpiotest-default-rtdb.firebaseio.com/'  # Replace with your Firebase database URL
})

# Reference to Firebase Realtime Database location
stream_ref = db.reference('live_stream')
events_ref = db.reference('events')  # New database node for detection events

# HLS Configuration
hls_folder = "/tmp/hls"  # Directory to store HLS segments
os.makedirs(hls_folder, exist_ok=True)  # Ensure directory exists

# FFmpeg command to start live streaming
ffmpeg_command = [
    "ffmpeg",
    "-f", "v4l2",
    "-input_format", "yuyv422",  # Use YUYV format
    "-video_size", "640x480",
    "-i", "/dev/video0",         # Input device
    "-c:v", "libx264",           # Encode to H.264
    "-preset", "ultrafast",      # Optimize for speed
    "-tune", "zerolatency",      # Low latency
    "-f", "hls",                 # Output format HLS
    "-hls_time", "1",            # Segment duration in seconds
    "-hls_list_size", "3",       # Keep only the last 3 segments
    "-hls_flags", "delete_segments",  # Delete old segments
    f"{hls_folder}/index.m3u8"   # Output HLS playlist
]

# Start FFmpeg as a subprocess
ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route('/')
def index():
    """Root page with an embedded HLS video player."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Stream</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    </head>
    <body>
        <h1>Live Stream</h1>
        <video id="videoPlayer" width="640" height="480" controls autoplay></video>
        <script>
            if (Hls.isSupported()) {
                var video = document.getElementById('videoPlayer');
                var hls = new Hls();
                hls.loadSource('/video/index.m3u8');
                hls.attachMedia(video);
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = '/video/index.m3u8';
            } else {
                alert("Your browser does not support HLS.");
            }
        </script>
        <p>If the video does not load, ensure your browser supports HLS or try a compatible device.</p>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/video/<path:filename>')
def video(filename):
    """Serve HLS playlist and segments."""
    return send_from_directory(hls_folder, filename)

def detect_objects():
    """Perform object detection on live stream frames."""
    # Haar Cascade for object detection (example: face detection)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # Capture video directly from the camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Unable to open video capture for object detection.")
        return

    print("Object detection started...")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Convert to grayscale for object detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"People detected at {timestamp}. Logging event to Firebase.")

            # Log detection event to Firebase
            events_ref.push({'event': 'people_detected', 'timestamp': timestamp})

        time.sleep(0.1)  # Slight delay for efficient processing

    cap.release()
    print("Object detection stopped.")

def log_stream_event(start=True):
    """Log stream start/stop event to Firebase."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    if start:
        stream_ref.push({'event': 'stream_started', 'timestamp': timestamp})
        print(f"Stream started at {timestamp}")
    else:
        stream_ref.push({'event': 'stream_ended', 'timestamp': timestamp})
        print(f"Stream ended at {timestamp}")

def get_local_ip():
    """Retrieve the local IP address of the Raspberry Pi."""
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    return local_ip

if __name__ == '__main__':
    try:
        # Log stream start
        log_stream_event(start=True)

        # Start object detection in a separate thread
        detection_thread = threading.Thread(target=detect_objects, daemon=True)
        detection_thread.start()

        # Get and print the HTTP server URL
        local_ip = get_local_ip()
        server_url = f"http://192.168.1.234:8000"
        print(f"Live stream available at: {server_url}")

        # Start Flask server
        print("Starting HTTP server on port 8000...")
        flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8000, debug=False), daemon=True)
        flask_thread.start()

        # Monitor for user input to stop the stream
        while True:
            user_input = input("Enter 'stop' to end the stream: ").strip().lower()
            if user_input == 'stop':
                print("Stopping the stream...")
                break

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Log stream end
        log_stream_event(start=False)

        # Terminate FFmpeg process
        ffmpeg_process.terminate()
        ffmpeg_process.wait()

        print("Program terminated.")
