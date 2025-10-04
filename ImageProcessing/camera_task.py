import asyncio
import threading
from typing import Any, Dict, Optional
from datetime import datetime

import cv2
from ultralytics import YOLO


class CameraTask:
    def __init__(self, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event,
                 results_q: Optional[asyncio.Queue] | None = None):
        self.loop = loop  # event loop to post back into
        self.stop_flag = threading.Event()  # thread-safe flag for this worker thread
        self.results_q = results_q  # optional queue to publish detections
        self._inited = False
        self.stop_event = stop_event or asyncio.Event()
        self.cap = None
        self.model = None

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

        self.payload = {}

        self.object_actions = {
        "gauge": self.handle_gauge,
        "gauge_tip": self.handle_gauge,
        "gauge_middle": self.handle_gauge,
        "valve_open": self.handle_valve_open,
        "valve_closed": self.handle_valve_closed,
        "marker": self.handle_marker
        }

        print("Starting webcam detection... Press 'q' to quit.")

    def _init_hw(self):
        # Load the YOLOv5 model
        self.model = YOLO('yolov5s.pt')  # Replace with custom model 'yolov5n.pt' once completed
        # Open webcam (0 = default camera) needs to be updated for the onboard camera not laptop webcam
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            print("Cannot open camera")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.stop_flag.set()
            return

    def shutdown(self):
        self.stop_flag.set()  # NEW: release resources here
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    def make_detector(self, dict_id):
            aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
            return cv2.aruco.ArucoDetector(aruco_dict, self.aruco_params)

    def autodetect_aruco_dict(self, gray):
            """Tries several common aruso dictionaries and returns the one with the most hits."""
            candidate_dicts = [
                cv2.aruco.DICT_4X4_50, cv2.aruco.DICT_4X4_100, cv2.aruco.DICT_4X4_250,
                cv2.aruco.DICT_5X5_50, cv2.aruco.DICT_5X5_100, cv2.aruco.DICT_5X5_250,
                cv2.aruco.DICT_6X6_50, cv2.aruco.DICT_6X6_100, cv2.aruco.DICT_6X6_250,
                cv2.aruco.DICT_APRILTAG_36h11  # include if your sheet might be AprilTags
            ]
            best = (None, -1, None)  # (dict_id, count, (corners, ids))
            for d in candidate_dicts:
                det = self.make_detector(d)
                corners, ids, _ = det.detectMarkers(gray)
                cnt = 0 if ids is None else len(ids)
                if cnt > best[1]:
                    best = (d, cnt, (corners, ids))
            return best

    # Make data available to other threads
    def _publish(self, payload: Dict[str, Any]) -> None:
        """Called on the event loop thread via call_soon_threadsafe."""
        if not self.results_q:
            return
        try:
            self.results_q.put_nowait(payload)  # non-blocking; may raise QueueFull
        except asyncio.QueueFull:
            # drop oldest / newest as desired; simplest: drop this one
            pass

    def handle_gauge(self):
        print("gauge")

    def handle_valve_open(self):
        print("valve_open")

    def handle_valve_closed(self):
        print("valve_closed")

    def handle_marker(self, frame, roi, info):
        print("marker")
        timestamp = datetime.now().isoformat()
        src = roi if roi is not None else frame

        # Skip tiny ROIs; use full frame if the crop is too small
        h, w = src.shape[:2]
        if min(h, w) < 60:
            src = frame  # fallback to full frame for robustness

        # Work in grayscale for detection
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

        if self.aruco_detector is None:
            dict_id, count, first = self.autodetect_aruco_dict(gray)
            if dict_id is not None and count > 0:
                self.aruco_dict_id = dict_id
                self.aruco_detector = self.make_detector(dict_id)

        corners, ids, _ = self.aruco_detector.detectMarkers(gray)
        self.payloads = {}

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(gray, corners, ids)
            self.payloads = {
                "timestamp": timestamp,
                "image": gray,
                "ArUco Marker id": ids, 
                "info": info
            }
        else:
            cv2.imshow("YOLOv5 Live", gray)
            print("YOLO said marker ≥80%, but no ArUco found")
    

    # Takes a imaged maked by YOLO box and returns just the box as a image
    # Reduces comput time as only box area is proccesed. 
    def _crop_roi(self, frame, xyxy):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, xyxy)
        x1 = max(0, min(w - 1, x1)); x2 = max(0, min(w, x2))
        y1 = max(0, min(h - 1, y1)); y2 = max(0, min(h, y2))
        if x2 <= x1 or y2 <= y1:
            return frame  # fallback
        return frame[y1:y2, x1:x2]
    
    #Turn images from cam into jpeg for sending to ques and using in website.
    def _encode_jpeg(self, img, quality: int = 85):
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buf.tobytes() if ok else None

    def step(self):
        if self.stop_event.is_set():  # NEW: quick exit if stopping
            return

        if not self._inited:
            self._init_hw()
            self._inited = True
            if self.stop_event.is_set():  # if init failed
                return

        success, frame = self.cap.read()
        if not success:
            print("⚠️ Failed to grab frame")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.stop_flag.set()
            return
        timestamp = datetime.now().isoformat()
        # Run inference on the frame (as a numpy array)
        self.results = self.model(frame, verbose=False)
        self.result = self.results[0]

        # Visualize detections on frame
        self.annotated_frame = self.result.plot()

        # Show frame in window
        cv2.imshow("YOLOv5 Live", self.annotated_frame)

        # detected_class_ids = result.boxes.cls.tolist() if result.boxes else []

        # class_names = [result.names[int(cls_id)] for cls_id in detected_class_ids]

        detected_any = False
        

        # Check if there are any detected boxes
        if self.result.boxes:
            # xyxy: (N,4), cls: (N,), conf: (N,)
            xyxy = self.result.boxes.xyxy.cpu().numpy()
            cls  = self.result.boxes.cls.cpu().numpy()
            conf = self.result.boxes.conf.cpu().numpy()

            for i in range(len(cls)):
                c = float(conf[i])
                if c < 0.9:
                    continue  # confidence threshhold (90%)

                cls_id = int(cls[i])
                name = self.result.names[cls_id].lower()
                bbox = xyxy[i]  # [x1,y1,x2,y2]

                action = self.object_actions.get(name)
                if not action:
                    continue

                roi = self._crop_roi(frame, bbox)
                info = {"name": name, "cls_id": cls_id, "conf": c, "bbox": bbox}
                action(frame, roi, info) # always the same call
                detected_any = True

        if(detected_any == False):
            self.payloads = {
                "timestamp": timestamp,
                "image": self.annotated_frame, 
            }
        

        if not detected_any:
            print("⚠️ No objects ≥80% confidence.")

        # Thread-safe handoff to the event loop -> queue
        if self.results_q:
            self.loop.call_soon_threadsafe(self._publish, self.payloads)

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.loop.call_soon_threadsafe(self.stop_event.set())
            self.stop_flag.set()
            return
        # Release resources
