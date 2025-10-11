# main.py 
# main file managing threads and tasks
# Author: Angela Scells
# Last Update: 08/10/2025 by Lily Stacey

from __future__ import annotations
import asyncio
import logging
import signal
from typing import Awaitable, Callable, Iterable

from flask import Flask, render_template, jsonify, send_from_directory
import threading
import queue
import base64
from datetime import datetime
import os

# ===================== Importing Drone tasks ===================== #
from Air_Quality.air_quality import AirQualityTask
from ImageProcessing.cameraTask import CameraTask



# ===================== Logging ===================== #
def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ===================== Task helpers ===================== #
AsyncOrSyncStep = Callable[[], Awaitable[None]] | Callable[[], None]

#A utility function to repeatedly run a function (async or sync) at fixed time intervals,
async def periodic(name: str, interval: float, step: AsyncOrSyncStep):
    logging.info(f"{name} started")
    try:
        while True:
            try:
                if asyncio.iscoroutinefunction(step):
                    await step()  # type: ignore[arg-type]
                else:
                    # Run blocking/sync work in a thread to avoid blocking the loop
                    await asyncio.to_thread(step)  # type: ignore[arg-type]
            except Exception as e:
                logging.exception(f"{name} error: {e}")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logging.info(f"{name} cancelled")
        raise

# ===================== Thread-safe Queue Adapter ===================== #
class ThreadQueueAdapter:
    """
    Minimal adapter that looks like an asyncio.Queue for the methods
    your tasks use, but is backed by thread-safe queue.Queue so Flask
    routes (running in another thread) can read safely.
    """
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()

    # matches asyncio.Queue API used by your tasks
    def put_nowait(self, item):
        self._q.put_nowait(item)

    def get_nowait(self):
        return self._q.get_nowait()

    def empty(self) -> bool:
        return self._q.empty()


class App:
    def __init__(self, stop_event: asyncio.Event, sensor_q: ThreadQueueAdapter, camera_q: ThreadQueueAdapter) -> None:
        self.tasks: list[asyncio.Task[None]] = []
        self.stopping = asyncio.Event()
        self.stop_event = stop_event
        self.cam: CameraTask | None = None
        self.aq: AirQualityTask | None = None
        self.sensor_q = sensor_q
        self.camera_q = camera_q
     
        

    async def start(self) -> None:
        # Example of register the air quality taks 
        loop = asyncio.get_running_loop()

        self.cam = CameraTask(
            loop=loop,
            stop_event=self.stop_event,
            results_q=self.camera_q,
        )
        self.aq = AirQualityTask(
            loop = loop,
            stop_event=self.stop_event,
            results_q=self.sensor_q,
        )

        self.tasks.append(asyncio.create_task(periodic("camera capturing", 0.2, self.cam.step)))
        self.tasks.append(asyncio.create_task(periodic("air quality reading", 2.0, self.aq.step)))
        logging.info("tasks started")

    async def stop(self) -> None:
        if self.stopping.is_set():
            return
        self.stopping.set()
        logging.info("stopping...")
        for t in self.tasks: 
            #t.shutdown()
            t.cancel()
        # Gather with return_exceptions to ensure all are awaited
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
             
        logging.info("all tasks stopped")

# ===================== Flask server (in a thread) ===================== #
def start_flask_server(sensor_q: ThreadQueueAdapter, camera_q: ThreadQueueAdapter, host="0.0.0.0", port=5000, debug=True):
    app = Flask(__name__)

    log_folder = "logs"
    os.makedirs(log_folder, exist_ok=True)

    @app.route("/api/sensor")
    def get_sensor():
        data = {}
        try:
            while not sensor_q.empty():
                data = sensor_q.get_nowait()
        except Exception:
            pass

        if data:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(log_folder, f"sensor_{ts}.txt")
            with open(filename, "w") as f:
                f.write(str(data))

        return jsonify(data)

    @app.route("/api/camera")
    def get_camera():
        data = {}
        try:
            while not camera_q.empty():
                data = camera_q.get_nowait()
        except Exception:
            pass

        if "image" in data:
            img_bytes = data["image"]
            if isinstance(img_bytes, bytes):
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                data["image"] = "data:image/jpeg;base64," + img_b64

        return jsonify(data)

    @app.route("/api/logs")
    def get_logs():
        files = sorted(os.listdir(log_folder), reverse=True)
        return jsonify(files)

    @app.route("/")
    def index():
        # ensure you have templates/index.html in your working dir
        return render_template("index.html")

    # Important: use_reloader=False so the server does not spawn a 2nd process
    app.run(host=host, port=port, debug=debug, use_reloader=False)

def run_flask_in_thread(sensor_q: ThreadQueueAdapter, camera_q: ThreadQueueAdapter) -> threading.Thread:
    t = threading.Thread(target=start_flask_server, args=(sensor_q, camera_q), daemon=True)
    t.start()
    return t
# ===================== Main ===================== #

async def amain() -> None:

    setup_logging()
    logging.info("app starting...")
    

    stop_called = asyncio.Event()

    # thread-safe queues (readable in Flask thread, writable from async tasks)
    sensor_q = ThreadQueueAdapter()
    camera_q = ThreadQueueAdapter()

    # start async tasks
    app = App(stop_event=stop_called, sensor_q=sensor_q, camera_q=camera_q)
    await app.start()

     # start Flask in background thread
    flask_thread = run_flask_in_thread(sensor_q, camera_q)
    logging.info(f"Flask server thread started: {flask_thread.name}")

    loop = asyncio.get_running_loop()

    def _signal_handler(signum, frame=None):
        logging.info(f"signal {signum} received")
        stop_called.set()

    #Signal handeling for Linx and Windows
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig)
        except NotImplementedError:
            # add_signal_handler can be unavailable on some platforms (e.g., Windows)
            signal.signal(sig, lambda s, f: _signal_handler(s))

    # Keep main alive until a signal arrives
    await stop_called.wait()
    await app.stop()
    logging.info("bye")

if __name__ == "__main__":
    asyncio.run(amain())
