from flask import Flask, render_template, send_from_directory, jsonify
import socket
import time

app = Flask(__name__)

hls_folder = '/home/pi/solareye'  # Update with the correct path
ffmpeg_process = None  # Placeholder for the ffmpeg process

@app.route('/')
def index():
    """Render the live stream webpage."""
    return render_template('livestream.html')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)