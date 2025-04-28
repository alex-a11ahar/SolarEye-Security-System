import subprocess
import os
import threading
from flask import Flask, send_from_directory, render_template_string, request, jsonify
import logging
import time
import socket
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
stream_ref = db.reference('live_stream')  # Node for logging stream events

# HLS Configuration
hls_folder = "/tmp/hls"  # Directory to store HLS segments
os.makedirs(hls_folder, exist_ok=True)  # Ensure directory exists

# FFmpeg process handle
ffmpeg_process = None

@app.route('/')
def index():
    """Root page with an embedded HLS video player and stop button."""
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
        <button id="stopButton">Stop Stream</button>
        <script>
            document.getElementById('stopButton').addEventListener('click', function() {
                fetch('/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => alert(data.message))
                .catch(error => console.error('Error:', error));
            });
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

@app.route('/stop', methods=['POST'])
def stop_stream():
    """Stop the live stream when the button is clicked."""
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process.wait()
        ffmpeg_process = None
        log_stream_event("livestream stopped")
        return jsonify({"message": "Stream has been stopped successfully."})
    else:
        return jsonify({"message": "Stream is not running."})

def get_local_ip():
    """Retrieve the local IP address of the Raspberry Pi."""
    try:
        # Create a dummy socket to determine the actual local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a public IP, no data is actually sent
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception as e:
        print(f"Error retrieving local IP: {e}")
        return "127.0.0.1"  # Default to localhost as a fallback

def log_stream_event(event_message):
    """Log stream start/stop event to Firebase with a timestamp."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    stream_ref.push({'event': event_message, 'timestamp': timestamp})
    print(f"{event_message.capitalize()} at {timestamp}")

def start_ffmpeg():
    """Start FFmpeg process for live streaming."""
    global ffmpeg_process
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
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == '__main__':
    try:
        # Start FFmpeg
        start_ffmpeg()

        # Log stream start to Firebase
        log_stream_event("livestream started")

        # Get and print the HTTP server URL
        local_ip = get_local_ip()
        server_url = f"http://{local_ip}:8000"
        print(f"Live stream available at: {server_url}")

        # Start Flask server in a separate thread
        flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8000, debug=False), daemon=True)
        flask_thread.start()

        # Terminal fallback for stopping the stream
        while True:
            user_input = input("Enter 'stop' to end the stream: ").strip().lower()
            if user_input == 'stop':
                if ffmpeg_process:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait()
                    log_stream_event("livestream stopped")
                    print("Stream has been stopped.")
                break

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Terminate FFmpeg process
        if ffmpeg_process:
            ffmpeg_process.terminate()
            ffmpeg_process.wait()
        print("Program terminated.")