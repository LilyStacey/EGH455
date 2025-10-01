import cv2
import asyncio
import threading
from ultralytics import YOLO
from typing import Any, Dict, Optional

class CameraTask:
    def __init__(self, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event, results_q: Optional[asyncio.Queue] | None = None):
        self.loop = loop                         # event loop to post back into
        self.stop_flag = threading.Event()       # thread-safe flag for this worker thread
        self.results_q = results_q               # optional queue to publish detections
        self._inited = False
        self.stop_event = stop_event or asyncio.Event()
        self.cap = None
        self.model = None

        print("Starting webcam detection... Press 'q' to quit.")

    def _init_hw(self):
        # Load the YOLOv5 model
        self.model = YOLO('yolov5s.pt') # Replace with custom model 'yolov5n.pt' once completed
        # Open webcam (0 = default camera) needs to be updated for the onboard camera not laptop webcam
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            print("Cannot open camera")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.stop_flag.set()
            return

    def shutdown(self):
        self.stop_flag.set()                                  # NEW: release resources here
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    #Make data available to other threads
    def _publish(self, payload: Dict[str, Any]) -> None:
        """Called on the event loop thread via call_soon_threadsafe."""
        if not self.results_q:
            return
        try:
            self.results_q.put_nowait(payload)  # non-blocking; may raise QueueFull
        except asyncio.QueueFull:
            # drop oldest / newest as desired; simplest: drop this one
            pass

    def step(self):
        if self.stop_event.is_set():                        # NEW: quick exit if stopping
            return
                
        if not self._inited:
            self._init_hw()
            self._inited = True
            if self.stop_event.is_set():                    # if init failed
                return
        
        success, frame = self.cap.read()
        if not success:
            print("⚠️ Failed to grab frame")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.stop_flag.set()                       
            return

        # Run inference on the frame (as a numpy array)
        self.results = self.model(frame, verbose=False)
        self.result = self.results[0]

        # Visualize detections on frame
        self.annotated_frame = self.result.plot()

        # Show frame in window
        cv2.imshow("YOLOv5 Live", self.annotated_frame)

        #detected_class_ids = result.boxes.cls.tolist() if result.boxes else []
                
        # class_names = [result.names[int(cls_id)] for cls_id in detected_class_ids]
            
        detected_class_ids = []
        class_names = []

        # Check if there are any detected boxes
        if self.result.boxes:
            for cls_id, conf in zip(self.result.boxes.cls, self.result.boxes.conf):
                if conf > 0.90: # confidence > 90%
                    detected_class_ids.append(int(cls_id))
                    class_names.append(self.result.names[int(cls_id)])

        if class_names:
            print(f"Detected objects: {', '.join(set(class_names))}")
        else:
            print("⚠️ No objects detected.")

        if self.result.boxes:
            for cls_id, conf in zip(self.result.boxes.cls, self.result.boxes.conf):
                if conf > 0.90:
                    detected_class_ids.append(int(cls_id))
                    class_names.append(self.result.names[int(cls_id)])

        payload = {
            "classes": detected_class_ids,
            "names": list(set(class_names)),
            "count": len(detected_class_ids),
        }

        # Thread-safe handoff to the event loop -> queue
        if self.results_q:
            self.loop.call_soon_threadsafe(self._publish, payload)

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.loop.call_soon_threadsafe(self.stop_event.set()) 
            self.stop_flag.set()
            return

        # Release resources
        
