from flask import Flask, jsonify, Response, render_template, send_from_directory
import asyncio, threading, datetime, os
import numpy as np
import cv2

from air_quality import AirQualityTask
from cameraTask import CameraTask

app = Flask(__name__, template_folder="templates")
BASE_LOG_DIR = "logs"

# Create session folder for logs
session_folder = os.path.join(BASE_LOG_DIR, datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
os.makedirs(session_folder, exist_ok=True)

# Async queues for sensor and camera data
sensor_queue = asyncio.Queue(maxsize=10)
camera_queue = asyncio.Queue(maxsize=1)

# ---- Helper functions ----
def save_sensor_log(data):
    filepath = os.path.join(session_folder, "sensor_log.csv")
    header = ",".join(data.keys())
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write(header + "\n")
    with open(filepath, "a") as f:
        f.write(",".join(str(v) for v in data.values()) + "\n")

# ---- Start AirQualityTask ----
def start_air_quality(loop):
    stop_event = asyncio.Event()
    task = AirQualityTask(loop, stop_event, results_q=sensor_queue)
    async def run():
        while not stop_event.is_set():
            await task.step()
            # Save log
            if not sensor_queue.empty():
                data = sensor_queue.get_nowait()
                save_sensor_log(data)
                await sensor_queue.put(data)  # put back for API
            await asyncio.sleep(1)
    loop.run_until_complete(run())

# ---- Start CameraTask ----
def start_camera(loop):
    stop_event = asyncio.Event()
    task = CameraTask(loop, stop_event, results_q=camera_queue)
    while not stop_event.is_set():
        task.step()

# ---- Flask Routes ----
@app.route("/")
def index():
    return render_template("backup.html")

@app.route("/api/sensors")
def api_sensors():
    if sensor_queue.empty():
        return jsonify({})
    data = sensor_queue.get_nowait()
    sensor_queue.put_nowait(data)
    return jsonify(data)

def generate_mjpeg():
    while True:
        if camera_queue.empty():
            frame = 255 * np.ones((480, 640, 3), dtype=np.uint8)
        else:
            payload = camera_queue.get_nowait()
            frame = payload.get("image")
            camera_queue.put_nowait(payload)
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

@app.route("/camera_feed")
def camera_feed():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/logs")
def logs():
    return jsonify(os.listdir(session_folder))

@app.route("/logs/<path:filename>")
def serve_log(filename):
    return send_from_directory(session_folder, filename)

# ---- Run server ----
if __name__=="__main__":
    loop = asyncio.new_event_loop()
    threading.Thread(target=start_air_quality, args=(loop,), daemon=True).start()
    threading.Thread(target=start_camera, args=(loop,), daemon=True).start()
    app.run(host="0.0.0.0", port=5000, threaded=True)
