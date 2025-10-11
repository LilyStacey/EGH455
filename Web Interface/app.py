# app.py
from flask import Flask, render_template, jsonify, send_file
import asyncio
from main import App  # your existing App class from main.py
import threading
import io
from PIL import Image

app = Flask(__name__)

# ===================== Shared App Instance ===================== #
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
stop_event = asyncio.Event()
my_app = App(stop_event=stop_event)

# Start the App (camera + sensors)
def start_async_app():
    loop.run_until_complete(my_app.start())
threading.Thread(target=start_async_app, daemon=True).start()


# ===================== DASHBOARD ROUTES ===================== #
@app.route("/")
def dashboard():
    return render_template("dashboard.html")  # your updated HTML file


@app.route("/data")
def get_data():
    """Return latest sensor and camera data as JSON"""
    data = my_app.latest_data.copy()  # copy for thread safety
    # Ensure all sensor keys exist
    for key in ["temp","hum","light","press","red_gas","ox_gas","nh3"]:
        if key not in data or data[key] is None:
            data[key] = 0.0
    # Camera info
    camera_payload = data.get("camera", {})
    data["target_found"] = bool(camera_payload.get("names"))
    data["target_type"] = ",".join(camera_payload.get("names", [])) if camera_payload.get("names") else "--"
    return jsonify(data)


@app.route("/camera_feed")
def camera_feed():
    """Return latest camera image"""
    camera_payload = my_app.latest_data.get("camera")
    if camera_payload and "frame" in camera_payload:
        # Convert frame (numpy array) to JPEG
        img = Image.fromarray(camera_payload["frame"])
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return send_file(buf, mimetype="image/jpeg")
    else:
        # Return placeholder
        return send_file("static/latest.jpg", mimetype="image/jpeg")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
