# main.py 
# main file managing threads and tasks
# Author: Angela Scells
# Last Update: 24/09/2025

from __future__ import annotations
import asyncio
import logging
import signal
from typing import Awaitable, Callable, Iterable

# ===================== Importing Drone tasks ===================== #
# from air_quality_task import AirQualityTask
from ImageProcessing.camera_task import CameraTask
# from ip_address_task import ipAddressTask
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
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        cam = CameraTask()

        # Example of register the air quality taks 
        self._tasks.append(asyncio.create_task(periodic("air-quality", 1.0, cam.step)))
        logging.info("tasks started")

    async def stop(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()
        logging.info("stopping…")
        for t in self._tasks:
            t.cancel()
        # Gather with return_exceptions to ensure all are awaited
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logging.info("all tasks stopped")

# ===================== Main ===================== #

async def amain() -> None:
    setup_logging()
    logging.info("app starting…")

    app = App()
    await app.start()

    loop = asyncio.get_running_loop()

    # Signals -> graceful cancellation
    stop_called = asyncio.Event()

    def _signal_handler(signum, frame=None):
        logging.info(f"signal {signum} received")
        stop_called.set()

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
