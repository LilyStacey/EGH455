# main.py 
# main file managing threads and tasks
# Author: Angela Scells
# Last Update: 08/10/2025 by Lily Stacey

from __future__ import annotations
import asyncio
import logging
import signal
from typing import Awaitable, Callable, Iterable

# ===================== Importing Drone tasks ===================== #
from Air_Quality.air_quality import AirQualityTask
from ImageProcessing.cameraTask import CameraTask
# from Web_interface_task import webInterfaceTask


# ===================== Logging ===================== #
def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ===================== Task helpers ===================== #
AsyncTask = Callable[[], Awaitable[None]]

#A utility function to repeatedly run a function (async or sync) at fixed time intervals,
async def periodic(name: str, interval: float, step: Callable[[], Awaitable[None]] | Callable[[], None]):
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

# ===================== Shutdown handling ===================== #

class App:
    def __init__(self, stop_event: asyncio.Event) -> None:
        self.tasks: list[asyncio.Task[None]] = []
        self.stopping = asyncio.Event()
        self.stop_event = stop_event
        self.cam: CameraTask | None = None
        self.aq: AirQualityTask | None = None
        self._results_q: asyncio.Queue = asyncio.Queue(maxsize=2)

    async def start(self) -> None:
        # Example of register the air quality taks 
        loop = asyncio.get_running_loop()
        self.cam = CameraTask(
            loop=loop,
            stop_event=self.stop_event,
            results_q=self._results_q,
        )
        self.aq = AirQualityTask(
            loop = loop,
            stop_event=self.stop_event,
            results_q=self._results_q,
        )
        self.tasks.append(asyncio.create_task(periodic("camera capturing", 0.2, self.cam.step)))
        self.tasks.append(asyncio.create_task(periodic("air quality reading", 2.0, self.aq.step)))
        logging.info("tasks started")

   # Inside App class, after starting cam and aq tasks
self.latest_data = {
    "camera": None,  
    "temp": None,
    "hum": None,
    "light": None,
    "press": None,
    "red_gas": None,
    "ox_gas": None,
    "nh3": None,
}

async def detection_consumer():
    while not self.stopping.is_set():
        try:
            # Wait for new payload from CameraTask or AirQualityTask
            payload = await asyncio.wait_for(self._results_q.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        try:
            # === Camera data ===
            if "names" in payload:
                self.latest_data["camera"] = payload  # store latest camera payload
                logging.info(f"Detected: {payload['names']} (count={payload['count']})")
            # === Air quality data ===
            for key in ["temp","hum","light","press","red_gas","ox_gas","nh3"]:
                if key in payload:
                    self.latest_data[key] = payload[key]
        finally:
            self._results_q.task_done()

# Create and start consumer task
self.tasks.append(asyncio.create_task(detection_consumer()))
logging.info("detection consumer started")

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

# ===================== Main ===================== #

async def amain() -> None:
    setup_logging()
    logging.info("app starting...")

    stop_called = asyncio.Event()

    app = App(stop_event=stop_called)
    await app.start()

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
