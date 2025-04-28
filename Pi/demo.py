#!/usr/bin/env python3
import time
import os
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

# ——— ADC calibration —————————————————————————————————————————————
DIVIDER_RATIO_A0     = 21.0
BATTERY_NOMINAL_V    = 12.8
CHARGING_THRESHOLD_V = 13.0
DIVIDER_RATIO_A2     = 40.0
V_ZERO               = 2.5
SENSITIVITY          = 0.1

# ——— ADC Setup ————————————————————————————————————————————————
i2c      = busio.I2C(board.SCL, board.SDA)
ads      = ADS.ADS1115(i2c)
chan_a0  = AnalogIn(ads, ADS.P0)
chan_a1  = AnalogIn(ads, ADS.P1)
chan_a2  = AnalogIn(ads, ADS.P2)
chan_a3  = AnalogIn(ads, ADS.P3)
window_a1 = deque(maxlen=10)
window_a3 = deque(maxlen=10)

# Telemetry thread control
events_stop        = threading.Event()
telem_thread        = None

# ——— Telemetry helper ———————————————————————————————————————————
def get_telemetry():
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

    return battery_v, status, soc, panel_v, i1, i3


def telemetry_loop():
    while not events_stop.is_set():
        batt_v, status, soc, panel_v, i1, i3 = get_telemetry()
        print(f"[Telemetry] Battery: {batt_v:.3f}V {status} SOC:{soc:.1f}% | \
              Panel: {panel_v:.3f}V | I1: {i1:.3f}A | I2: {i3:.3f}A")
        time.sleep(1)

# ——— Firebase Initialization —————————————————————————————————————
cred = credentials.Certificate(CRED_PATH)
firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})
db               = firestore.client()
bucket           = storage.bucket()
pir_ref          = db.collection('pir_sensor_data')
video_ref        = db.collection('video_sensor_data')
mode_ref         = db.collection('control').document('operation_mode')
led_ref          = db.collection('control').document('led_control')

# init control docs
try:
    led_ref.set({'state': 0}, merge=True)
    mode_ref.set({'mode': 1}, merge=True)
except Exception as e:
    print(f"[INIT] {e}")

# ——— Hardware Setup ————————————————————————————————————————————
pir   = MotionSensor(14)
led   = LED(17)
led.off()
atexit.register(led.off)

# ——— State Variables ————————————————————————————————————————————
current_mode      = None
motion_active     = False
recording_process = None
ffmpeg_process    = None
last_clip         = [None]

# ——— Mode 0 handlers ————————————————————————————————————————————
def mode0_motion():
    global motion_active, last_pir_event, telem_thread
    now = time.time()
    if now - last_pir_event < PIR_DEBOUNCE:
        return
    last_pir_event = now
    motion_active = True
    led.on()
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Mode0: motion detected, LED ON")
    # start telemetry
    global telem_thread
    if telem_thread is None or not telem_thread.is_alive():
        events_stop.clear()
        telem_thread = threading.Thread(target=telemetry_loop, daemon=True)
        telem_thread.start()
    try:
        pir_ref.add({'motion':'detected','timestamp':ts})
        video_ref.add({'video_url':'','timestamp':ts})
    except:
        pass


def mode0_no_motion():
    global motion_active, last_pir_event, telem_thread
    now = time.time()
    if now - last_pir_event < PIR_DEBOUNCE:
        return
    last_pir_event = now
    motion_active = False
    led.off()
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Mode0: motion stopped, LED OFF")
    # stop telemetry
    events_stop.set()
    telem_thread = None
    try:
        pir_ref.add({'motion':'stopped','timestamp':ts})
        video_ref.add({'video_url':'','timestamp':ts})
    except:
        pass

# ——— Mode 1 handlers ————————————————————————————————————————————
def start_recording():
    global recording_process
    ts = time.strftime('%Y%m%d_%H%M%S')
    h264 = f"/tmp/video_{ts}.h264"
    mp4  = f"/tmp/video_{ts}.mp4"
    recording_process = subprocess.Popen([
        'libcamera-vid','-t','0','--width','1280','--height','720',
        '--framerate','24','--output',h264
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    led.on()
    print(f"[{ts}] Mode1: recording started")
    return (h264,mp4)

def stop_recording(clip):
    global recording_process
    led.off()
    if recording_process:
        recording_process.terminate()
        recording_process.wait()
        recording_process=None
    if clip:
        h264,mp4=clip
        subprocess.run([
            'ffmpeg','-y','-framerate','24','-i',h264,
            '-c:v','libx264','-preset','fast','-pix_fmt','yuv420p',mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            blob=bucket.blob(f"videos/{os.path.basename(mp4)}")
            blob.upload_from_filename(mp4)
            blob.make_public()
            video_ref.add({'video_url':blob.public_url,'timestamp':time.strftime('%Y-%m-%d %H:%M:%S')})
        except:
            pass
        os.remove(h264)
        os.remove(mp4)
    print("Mode1: recording stopped")

# ——— Flask & Mode2 —————————————————————————————————————————————
app=Flask(__name__)
@app.route('/')
def index():
    html="""
<html><body>
<video id='v' width=720 height=480 controls autoplay muted playsinline></video>
<script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
<script>
 var v=document.getElementById('v');
 if(Hls.isSupported()){var h=new Hls();h.loadSource('/video/index.m3u8');h.attachMedia(v);h.on(Hls.Events.MANIFEST_PARSED,()=>v.play());}
 else{v.src='/video/index.m3u8';}
</script></body></html>
"""
    return Response(html, mimetype='text/html')
@app.route('/video/<path:fn>')
def video_route(fn):
    path=os.path.join(HLS_FOLDER,fn)
    if not os.path.exists(path):abort(404)
    mime='application/vnd.apple.mpegurl' if fn.endswith('.m3u8') else 'video/MP2T'
    return send_from_directory(HLS_FOLDER,fn,mimetype=mime)

def start_stream():
    global ffmpeg_process
    print("Mode2: starting stream")
    os.makedirs(HLS_FOLDER,exist_ok=True)
    for f in os.listdir(HLS_FOLDER):os.remove(os.path.join(HLS_FOLDER,f))
    if os.path.exists(FIFO_PATH):os.remove(FIFO_PATH)
    os.mkfifo(FIFO_PATH)
    subprocess.Popen([
        'libcamera-vid','-t','0','--width','1280','--height','720',
        '--framerate','24','--inline','--profile','baseline','--level','4','--output',FIFO_PATH
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ffmpeg_process=subprocess.Popen([
        'ffmpeg','-hide_banner','-loglevel','error','-f','h264','-i',FIFO_PATH,
        '-preset','ultrafast','-g','24','-sc_threshold','0','-c:v','copy',
        '-f','hls','-hls_time','1','-hls_list_size','6',
        '-hls_flags','delete_segments+program_date_time+independent_segments',
        '-hls_allow_cache','0',f"{HLS_FOLDER}/index.m3u8"
    ],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print("Mode2: pipeline up")

def stop_stream():
    global ffmpeg_process
    if ffmpeg_process:ffmpeg_process.terminate();ffmpeg_process.wait();ffmpeg_process=None
    if os.path.exists(FIFO_PATH):os.remove(FIFO_PATH)
    print("Mode2: stopped")

# ——— Mode & LED monitoring —————————————————————————————————————
def monitor_mode():
    global current_mode
    last_clip=[None]
    _noop=lambda:None
    while True:
        try:
            m=mode_ref.get().to_dict().get('mode',0)
            if m not in (0,1,2):mode_ref.update({'mode':1});m=1
            if m!=current_mode:
                print(f"Mode {current_mode}->{m}")
                # teardown
                led.off()
                if current_mode==1 and last_clip[0]:stop_recording(last_clip[0]);last_clip[0]=None
                if current_mode==2:stop_stream()
                if current_mode==0:events_stop.set();telem_thread=None
                # setup
                if m==0:
                    pir.when_motion=mode0_motion;pir.when_no_motion=mode0_no_motion
                elif m==1:
                    pir.when_motion=lambda: last_clip.__setitem__(0,start_recording())
                    pir.when_no_motion=lambda: (stop_recording(last_clip[0]),last_clip.__setitem__(0,None))
                else:
                    pir.when_motion=_noop;pir.when_no_motion=_noop;start_stream()
                current_mode=m
        except Exception as e:
            print(f"[MODE] {e}")
        time.sleep(2 if current_mode==0 else 3)

def monitor_led():
    global motion_active,recording_process
    blink=False
    while True:
        try:
            state=led_ref.get().to_dict().get('state',0)
            in_use=motion_active or bool(recording_process)
            if state==1 and not in_use and not blink:
                led.blink(on_time=LED_BLINK_ON,off_time=LED_BLINK_OFF,background=True);blink=True
            elif blink and (state==0 or in_use):
                led.on() if in_use else led.off();blink=False
        except:
            pass
        time.sleep(0.5)

if __name__=="__main__":
    threading.Thread(target=monitor_mode,daemon=True).start()
    threading.Thread(target=monitor_led,daemon=True).start()
    print(f"Serving on http://0.0.0.0:{HTTP_PORT}")
    app.run(host="0.0.0.0",port=HTTP_PORT)