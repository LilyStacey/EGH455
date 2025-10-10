from flask import Flask, render_template, jsonify, send_from_directory
import asyncio
import threading
import queue
import base64
from datetime import datetime
import os

from air_quality import AirQualityTask
from camera_task import CameraTask

app = Flask(__name__)

sensor_queue = asyncio.Queue()
camera_queue = asyncio.Queue()

log_folder = "logs"
os.makedirs(log_folder, exist_ok=True)

# --- START BACKGROUND THREADS ---
loop = asyncio.new_event_loop()
stop_event = asyncio.Event()

air_task = AirQualityTask(loop=loop, stop_event=stop_event, results_q=sensor_queue)
camera_task = CameraTask(loop=loop, stop_event=stop_event, results_q=camera_queue)

def run_loop():
    asyncio.set_event_loop(loop)
    async def loop_tasks():
        while not stop_event.is_set():
            await air_task.step()
            camera_task.step()
            await asyncio.sleep(0.1)
    loop.run_until_complete(loop_tasks())

t = threading.Thread(target=run_loop)
t.start()
# --- END BACKGROUND THREADS ---

# API endpoints
@app.route('/api/sensor')
def get_sensor():
    data = {}
    try:
        while not sensor_queue.empty():
            data = sensor_queue.get_nowait()
    except:
        pass

    # Save log
    if data:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(log_folder, f"sensor_{ts}.txt")
        with open(filename, "w") as f:
            f.write(str(data))

    return jsonify(data)

@app.route('/api/camera')
def get_camera():
    data = {}
    try:
        while not camera_queue.empty():
            data = camera_queue.get_nowait()
    except:
        pass

    if "image" in data:
        img_bytes = data["image"]
        if isinstance(img_bytes, bytes):
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            data["image"] = "data:image/jpeg;base64," + img_b64

    return jsonify(data)

@app.route('/api/logs')
def get_logs():
    files = sorted(os.listdir(log_folder), reverse=True)
    return jsonify(files)

# Serve frontend
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
