# Implements target acquisition & image processing functionality
# Author: Angela Scells
# Last Update: 08/10/2025 by Hunter Wilde

import asyncio
import math
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image
from inference_sdk import InferenceHTTPClient
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

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        # self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.aruco_detector = None

        self.payload = {}

        self.object_actions = {
            "gauge": self.handle_gauge,
            "needle_tip": self.handle_gauge,
            "gauge_centre": self.handle_gauge,
            "valve_open": self.handle_valve_open,
            "valve_closed": self.handle_valve_closed,
            "marker": self.handle_marker
        }

        print("Starting webcam detection... Press 'q' to quit.")

    def _init_hw(self):
        # Load the YOLOv5 model
        #self.model = YOLO('yolov5s.pt')  # Replace with custom model 'yolov5n.pt' once completed

        # Connect to the roboflow API
        self.model = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key="tD2CNvbXmeLSQZ5QGdup"
        )

        # Open webcam (0 = default camera) needs to be updated for the onboard camera not laptop webcam
        self.cap = cv2.VideoCapture(23) # On bottom USB3 port, 23-26, 31-34 were identifiable

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

    def renderAnnotatedGuage(self, coordinate, frame, info, theta):
        # Writes text and boxes on each frame - used for boxes, degrees, and psi
        for label_index, label in info["name"]:
            if "gauge_centre" in label:
                info[label_index] = label + " " + str(theta) + " deg"
            if "needle_tip" in label:
                psi = int(15.21 * theta - 638.21)  # TODO: Fill out the right values
                info[label_index] = label + " " + str(psi) + " psi"
        for object_coordinate_index, object_coordinate in enumerate(coordinate):
            # Recangle settings
            start_point = (int(object_coordinate[0]), int(object_coordinate[1]))
            end_point = (int(object_coordinate[2]), int(object_coordinate[3]))
            color_1 = (255, 0, 255)  # Magenta
            color_2 = (255, 255, 255)  # White
            thickness = 1

            cv2.rectangle(frame, start_point, end_point, color_1, thickness)

            # For text
            start_point_text = (start_point[0], max(start_point[1] - 5, 0))
            font = cv2.FONT_HERSHEY_SIMPLEX
            fontScale = 0.5
            thickness = 1

            cv2.putText(
                frame,
                info[name[object_coordinate_index]],
                start_point_text,
                font,
                fontScale,
                color_2,
                thickness
            )

    # mask_text and ocr_numbers_from_mask are additional function for the identification of the guage text
    # mask_text takes either red or black and and will singel out the text with that particular colour
    def mask_text(frame, color='red'):
        "Return a binary mask for red or black text"
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        if color == 'red':
            # Two hue bands for red
            lower1 = np.array([0, 90, 80], np.uint8)
            upper1 = np.array([10, 255, 255], np.uint8)
            lower2 = np.array([170, 90, 80], np.uint8)
            upper2 = np.array([180, 255, 255], np.uint8)
            m1 = cv2.inRange(hsv, lower1, upper1)
            m2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(m1, m2)
        else:
            # Black/gray: low value & low saturation (exclude colored stuff)
            # Tweak thresh if needed
            s, v = hsv[:, :, 1], hsv[:, :, 2]
            mask = cv2.inRange(s, 0, 60) & cv2.inRange(v, 0, 120)

        # Clean small noise
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return mask

    # tesseract_psm = 7 for small dissconneced text good for the guage numbers
    def ocr_numbers_from_mask(img_bgr, mask, tesseract_psm=7):
        "OCR masked regions; returns list of (numbers, bbox)."
        # keep only masked pixels
        masked = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)
        gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        # binary for OCR; Tesseract prefers dark text on light bg
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if (th == 0).sum() < (th == 255).sum():
            th = cv2.bitwise_not(th)

        # find candidate regions
        contours, _ = cv2.findContours((th < 128).astype(np.uint8) * 255,
                                       cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        H, W = th.shape
        cfg = f"--oem 3 --psm {tesseract_psm} -c tessedit_char_whitelist=0123456789"
        out = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h < 150 or h < 12:
                continue
            pad = 4
            x0, y0 = max(x - pad, 0), max(y - pad, 0)
            x1, y1 = min(x + w + pad, W), min(y + h + pad, H)
            crop = th[y0:y1, x0:x1]

            # quick deskew per region
            rect = cv2.minAreaRect(cnt)
            angle = rect[2]
            if angle < -45: angle += 90
            M = cv2.getRotationMatrix2D(((x1 - x0) // 2, (y1 - y0) // 2), angle, 1.0)
            crop = cv2.warpAffine(crop, M, (x1 - x0, y1 - y0),
                                  flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=255)

            txt = pytesseract.image_to_string(crop, config=cfg).strip()
            digits = "".join(ch for ch in txt if ch.isdigit())
            if digits:
                out.append((digits, [int(x0), int(y0), int(x1), int(y1)]))
        return out

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

    def handle_gauge(self, frame, detections, full_context):
        for det in full_context:
            name = det["name"].lower()
            if name == "centre":
                center_bbox = det["bbox"]
            elif name == "needle_tip":
                needle_bbox = det["bbox"]
        if center_bbox is not None and needle_bbox is not None:
            center_x_side_center = center_bbox[0] + ((center_bbox[2] - center_bbox[0]) / 2)
            center_y_side_center = center_bbox[1] + ((center_bbox[3] - center_bbox[1]) / 2)

            tip_x_side_center = needle_bbox[0] + ((needle_bbox[2] - needle_bbox[0]) / 2)
            tip_y_side_center = needle_bbox[1] + ((needle_bbox[3] - needle_bbox[1]) / 2)

            dy = tip_y_side_center - center_y_side_center
            dx = tip_x_side_center - center_x_side_center
            theta = math.atan2(dy, dx)
            theta = math.degrees(theta)
            theta = round(theta)

            # Changes negative theta to appropriate value
            if theta < 0:
                theta *= -1
                theta = (180 - theta) + 180

            # Sets new starting point
            theta = theta - 90

            # Changes negative theta to appropriate value
            if theta < 0:
                theta *= -1
                theta = theta + 270

            # theta of 74 is 500 psi and theta of 173 is 2,000 psi
            if theta <= 74 or theta >= 173:
                Drill_Trigger = False

    def handle_valve_open(self, frame, detections, full_context):
        timestamp = datetime.now().isoformat()
        cv2.imshow("YOLOv5 Live", frame)
        self.payload = {
            "timestamp": timestamp,
            "image": frame,
            "info": detections,
            "Valve_position": "open",
        }

    def handle_valve_closed(self, frame, detections, full_context):
        timestamp = datetime.now().isoformat()
        cv2.imshow("YOLOv5 Live", frame)
        self.payload = {
            "timestamp": timestamp,
            "image": frame,
            "info": detections,
            "Valve_position": "closed",
        }

    def handle_marker(self, frame, detections, full_context):
        timestamp = datetime.now().isoformat()
        for det in detections:
            src = det["roi"] if det["roi"] is not None else frame
            # Skip tiny ROIs; use full frame if the crop is too small
            h, w = src.shape[:2]
            if min(h, w) < 60:
                src = frame  # fallback to full frame for robustness

        # Work in grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.aruco_detector is None:
            dict_id, count, first = self.autodetect_aruco_dict(gray)
            if dict_id is not None and count > 0:
                self.aruco_dict_id = dict_id
                self.aruco_detector = self.make_detector(dict_id)
        corners, ids, _ = self.aruco_detector.detectMarkers(gray)
        self.payload = {}

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            cv2.imshow("YOLOv5 Live", frame)
            self.payload = {
                "timestamp": timestamp,
                "image": gray,
                "info": detections,
                "ArUco_Marker_id": ids
            }
        else:
            cv2.imshow("YOLOv5 Live", gray)
            print("YOLO said marker ≥80%, but no ArUco found")
        return self.payload

    # Takes a imaged maked by YOLO box and returns just the box as a image
    # Reduces comput time as only box area is proccesed. 
    def _crop_roi(self, frame, xyxy):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, xyxy)
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h, y2))

        return frame if x2 <= x1 or y2 <= y1 else frame[y1:y2, x1:x2]  # fallback

    # Turn images from cam into jpeg for sending to ques and using in website.
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
            print("Failed to grab frame")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.stop_flag.set()
            return

        # run inference on a local image (from roboflow)
        print(self.model.infer(
            frame,
            model_id="gauge-video-frames-mocuo/2"
        ))

        timestamp = datetime.now().isoformat()

        # FOR TESTING Aruco Markers!!!!
        # frame = cv2.imread("ImageProcessing\singlemarkersoriginal.jpg")

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
        grouped = defaultdict(list)

        # Check if there are any detected boxes
        if getattr(self.result, "boxes", None) and len(self.result.boxes) > 0:
            # xyxy: (N,4), cls: (N,), conf: (N,)
            xyxy = self.result.boxes.xyxy.cpu().numpy()
            cls = self.result.boxes.cls.cpu().numpy()
            conf = self.result.boxes.conf.cpu().numpy()

            for bbox, cls_id, c in zip(xyxy, cls, conf):
                c = float(c)
                if c < 0.9:
                    continue
                cls_id = int(cls_id)
                name = self.result.names[cls_id].lower()
                action = self.object_actions.get(name)
                if not action:
                    continue
                roi = self._crop_roi(frame, bbox)
                detected_any = True
                grouped[action].append({
                    "name": name,
                    "cls_id": cls_id,
                    "conf": c,
                    "bbox": bbox,
                    "roi": roi
                })

            # Save the current frame’s boxes
            self.current_detections = [d for batch in grouped.values() for d in batch]

            # Call each action once with its batch
            for action, detections in grouped.items():
                # Action is gotten from object_actions list and is based on the returned text of cls from YOLO image
                # full_context = self.current_detections contails all info on other boxes
                full_context = self.current_detections
                payload = action(self.annotated_frame, detections, full_context)
                if payload is None:
                    continue

        if not detected_any:
            self.payload = {
                "timestamp": timestamp,
                "image": self.annotated_frame,
            }

        if not detected_any:
            print("No objects >=80% confidence.")

        # Thread-safe handoff to the event loop -> queue
        if self.results_q:
            self.loop.call_soon_threadsafe(self._publish, self.payload)

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.loop.call_soon_threadsafe(self.stop_event.set())
            self.stop_flag.set()
            return

        # Release resources
