#!/usr/bin/env python3
import time
import os
import socket
import subprocess
import threading
import atexit
from collections import deque

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

import firebase_admin
from firebase_admin import credentials, firestore, storage
from gpiozero import MotionSensor, LED
from flask import Flask, Response, send_from_directory, abort

# ——— Configuration ——————————————————————————————————————————————
CRED_PATH        = "solareye_credentials.json"
STORAGE_BUCKET   = "solareye-security-system.firebasestorage.app"
HLS_FOLDER       = "/tmp/hls"
FIFO_PATH        = "/tmp/vidpipe.h264"
LED_BLINK_ON     = 0.1    # deterrence blink on duration (s)
LED_BLINK_OFF    = 0.1    # deterrence blink off duration (s)
HTTP_PORT        = 8000   # port for HTTP

# Debounce settings
PIR_DEBOUNCE     = 0.5    # seconds between PIR events
last_pir_event   = 0.0

# ——— ADC calibration (optional telemetry) ——————————————————————————————
DIVIDER_RATIO_A0     = 21.0
BATTERY_NOMINAL_V    = 12.8
CHARGING_THRESHOLD_V = 13.0
DIVIDER_RATIO_A2     = 40.0
V_ZERO               = 2.5
SENSITIVITY          = 0.1

# ——— ADC Setup ————————————————————————————————————————————————
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan_a0 = AnalogIn(ads, ADS.P0)
chan_a1 = AnalogIn(ads, ADS.P1)
chan_a2 = AnalogIn(ads, ADS.P2)
chan_a3 = AnalogIn(ads, ADS.P3)
window_a1 = deque(maxlen=10)
window_a3 = deque(maxlen=10)

def get_telemetry():
    """(Optional) read & smooth voltages/currents."""
    v0 = chan_a0.voltage
    battery_v = v0 * DIVIDER_RATIO_A0
    soc = max(0.0, min((battery_v / BATTERY_NOMINAL_V) * 100.0, 100.0))
    status = "Charging" if battery_v > CHARGING_THRESHOLD_V else "Discharging"

    v1 = chan_a1.voltage
    raw_i1 = (v1 - V_ZERO) / SENSITIVITY
    window_a1.append(raw_i1)
    i1 = sum(window_a1) / len(window_a1)

    v2 = chan_a2.voltage
    panel_v = v2 * DIVIDER_RATIO_A2

    v3 = chan_a3.voltage
    raw_i3 = (v3 - V_ZERO) / SENSITIVITY
    window_a3.append(raw_i3)
    i3 = sum(window_a3) / len(window_a3)

    return {
        'battery_voltage': round(battery_v, 3),
        'battery_soc':      round(soc, 1),
        'battery_status':   status,
        'panel_voltage':    round(panel_v, 3),
        'current_1':        round(i1, 3),
        'current_2':        round(i3, 3),
    }

# ——— Firebase Initialization —————————————————————————————————————
cred = credentials.Certificate(CRED_PATH)
firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})
db               = firestore.client()
bucket           = storage.bucket()
pir_sensor_ref   = db.collection('pir_sensor_data')
video_sensor_ref = db.collection('video_sensor_data')
mode_ref         = db.collection('control').document('operation_mode')
led_control_ref  = db.collection('control').document('led_control')
livestream_ref   = db.collection('control').document('livestream')

# Initialize control docs: set mode=1, led_control=0
try:
    led_control_ref.set({'state': 0}, merge=True)
    mode_ref.set({'mode': 1}, merge=True)
except Exception as e:
    print(f"[INIT] Error initializing control docs: {e}")

# ——— Hardware Setup ————————————————————————————————————————————
pir = MotionSensor(14)
led = LED(17)
led.off()
atexit.register(led.off)  # ensure LED off on exit

# ——— State Variables ————————————————————————————————————————————
current_mode      = None
motion_active     = False
recording_process = None
ffmpeg_process    = None

# ——— Mode 0: motion-only detection ——————————————————————————————————
def mode0_motion():
    global motion_active, last_pir_event
    now = time.time()
    if now - last_pir_event < PIR_DEBOUNCE:
        return
    last_pir_event = now

    motion_active = True
    led.on()
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Mode0: motion detected, LED ON")
    try:
        pir_sensor_ref.add({'motion': 'detected', 'timestamp': ts})
        video_sensor_ref.add({'video_url': '', 'timestamp': ts})
        print(f"[Mode0] logged to Firestore")
    except Exception as e:
        print(f"[Mode0] log error: {e}")

def mode0_no_motion():
    global motion_active, last_pir_event
    now = time.time()
    if now - last_pir_event < PIR_DEBOUNCE:
        return
    last_pir_event = now

    motion_active = False
    led.off()
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Mode0: motion stopped, LED OFF")
    try:
        pir_sensor_ref.add({'motion': 'stopped', 'timestamp': ts})
        video_sensor_ref.add({'video_url': '', 'timestamp': ts})
        print(f"[Mode0] stop logged to Firestore")
    except Exception as e:
        print(f"[Mode0] stop log error: {e}")

# ——— Mode 1: video recording ——————————————————————————————————————
def start_recording():
    global recording_process
    now = time.time()
    if now - last_pir_event < PIR_DEBOUNCE:
        return None
    ts   = time.strftime('%Y%m%d_%H%M%S')
    h264 = f"/tmp/video_{ts}.h264"
    mp4  = f"/tmp/video_{ts}.mp4"
    recording_process = subprocess.Popen([
        "libcamera-vid","-t","0","--width","1280","--height","720",
        "--framerate","24","--output", h264
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    led.on()
    print(f"[{ts}] Mode1: recording started, LED ON")
    return (h264, mp4)

def stop_recording(clip):
    global recording_process
    if recording_process:
        recording_process.terminate()
        recording_process.wait()
        recording_process = None
    if clip:
        h264, mp4 = clip
        subprocess.run([
            "ffmpeg","-y","-framerate","24","-i",h264,
            "-c:v","libx264","-preset","fast","-pix_fmt","yuv420p",mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            blob = bucket.blob(f"videos/{os.path.basename(mp4)}")
            blob.upload_from_filename(mp4)
            blob.make_public()
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            video_sensor_ref.add({'video_url': blob.public_url, 'timestamp': ts})
            print(f"[{ts}] Mode1: uploaded & logged to Firestore")
        except Exception as e:
            print(f"[Mode1] upload error: {e}")
        for f in (h264, mp4):
            try: os.remove(f)
            except: pass
    led.off()
    print("Mode1: recording stopped, LED OFF")

# ——— Mode 2: HLS livestream ———————————————————————————————————————
app = Flask(__name__)

@app.route('/')
def index():
    return Response(
        """
        <!DOCTYPE html><html><head><title>Live</title>
        <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script></head>
        <body><video id=v width=720 height=480 controls autoplay muted playsinline></video>
        <script>
        var v=document.getElementById('v');
        if(Hls.isSupported()){
          var h=new Hls(); h.loadSource('/video/index.m3u8');
          h.attachMedia(v); h.on(Hls.Events.MANIFEST_PARSED,()=>v.play());
        } else { v.src='/video/index.m3u8'; }
        </script></body></html>
        """, mimetype='text/html'
    )

@app.route('/video/<path:fn>')
def video_route(fn):
    path = os.path.join(HLS_FOLDER, fn)
    if not os.path.exists(path): abort(404)
    mime = 'application/vnd.apple.mpegurl' if fn.endswith('.m3u8') else 'video/MP2T'
    return send_from_directory(HLS_FOLDER, fn, mimetype=mime)

def start_stream():
    global ffmpeg_process
    print("Mode2: starting HLS livestream")
    os.makedirs(HLS_FOLDER, exist_ok=True)
    for f in os.listdir(HLS_FOLDER):
        os.remove(os.path.join(HLS_FOLDER, f))
    if os.path.exists(FIFO_PATH): os.remove(FIFO_PATH)
    os.mkfifo(FIFO_PATH)

    subprocess.Popen([
        "libcamera-vid","-t","0",
        "--width","1280","--height","720",
        "--framerate","24","--inline",
        "--profile","baseline","--level","4",
        "--output", FIFO_PATH
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ffmpeg_process = subprocess.Popen([
        "ffmpeg","-hide_banner","-loglevel","error",
        "-f","h264","-i", FIFO_PATH,
        "-preset","ultrafast","-g","24","-sc_threshold","0",
        "-c:v","copy","-f","hls","-hls_time","1",
        "-hls_list_size","6",
        "-hls_flags","delete_segments+program_date_time+independent_segments",
        "-hls_allow_cache","0", f"{HLS_FOLDER}/index.m3u8"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Mode2: HLS pipeline up")

def stop_stream():
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate(); ffmpeg_process.wait(); ffmpeg_process=None
    if os.path.exists(FIFO_PATH): os.remove(FIFO_PATH)
    print("Mode2: livestream stopped")

# ——— Mode & LED Monitoring ———————————————————————————————————————
def monitor_mode():
    global current_mode
    last_clip = None

    def _noop(): pass

    while True:
        try:
            m = mode_ref.get().to_dict().get('mode', 0)
            if m not in (0, 1, 2):
                print(f"[MODE] invalid {m} → resetting to 1")
                mode_ref.update({'mode': 1})
                m = 1

            if m != current_mode:
                print(f"[MODE] {current_mode} → {m}")
                led.off()

                # teardown previous
                if current_mode == 1 and last_clip:
                    stop_recording(last_clip); last_clip=None
                elif current_mode == 2:
                    stop_stream()

                # setup new
                if m == 0:
                    print("[MODE] Low Power Mode")
                    pir.when_motion, pir.when_no_motion = mode0_motion, mode0_no_motion

                elif m == 1:
                    print("[MODE] Default Mode (video on motion)")
                    def on_motion():
                        nonlocal last_clip
                        print("[Default] motion detected → start recording")
                        last_clip = start_recording()
                    def on_no_motion():
                        nonlocal last_clip
                        print("[Default] motion stopped → stop recording")
                        stop_recording(last_clip)
                        last_clip = None
                    pir.when_motion = on_motion
                    pir.when_no_motion = on_no_motion

                elif m == 2:
                    print("[MODE] Livestreaming Mode")
                    pir.when_motion = _noop
                    pir.when_no_motion = _noop
                    start_stream()

                current_mode = m

        except Exception as e:
            print(f"[MODE] error: {e}")

        time.sleep(2 if current_mode == 0 else 3)

def monitor_led_control():
    global motion_active, recording_process
    blinking = False
    while True:
        try:
            state  = led_control_ref.get().to_dict().get('state', 0)
            in_use = motion_active or bool(recording_process)
            if state == 1 and not in_use and not blinking:
                print("[LED] start deterrence blink")
                led.blink(on_time=LED_BLINK_ON, off_time=LED_BLINK_OFF, background=True)
                blinking = True
            elif blinking and (state == 0 or in_use):
                print("[LED] stop deterrence blink")
                led.on() if in_use else led.off()
                blinking = False
        except Exception as e:
            print(f"[LED] error: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    threading.Thread(target=monitor_mode, daemon=True).start()
    threading.Thread(target=monitor_led_control, daemon=True).start()
    print(f"Serving Flask on http://0.0.0.0:{HTTP_PORT}")
    app.run(host="0.0.0.0", port=HTTP_PORT)
