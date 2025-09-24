from ultralytics import YOLO
import cv2
import asyncio  


class CameraTask:
    def __init__(self,stop_event: asyncio.Event | None = None):
        self._inited = False
        print("Starting webcam detection... Press 'q' to quit.")
        self.stop_event = stop_event or asyncio.Event()
        self.cap = None

    def _init_hw(self):

        # Load the YOLOv5 model
        self.model = YOLO('yolov5s.pt')  # Replace with custome model 'yolov5n.pt' once completed

        #Open webcam (0 = default camera) needs to be updated for the on board camera not laptop webcame
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            print("Cannot open camera")
            self.stop_event.set()                       
            return
        

    def shutdown(self):                                   # NEW: release resources here
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

        
        # Processing video frames in a loop

    def step(self):
        if self.stop_event.is_set():                      # NEW: quick exit if stopping
            return
                
        if not self._inited:
            self._init_hw()
            self._inited = True
            if self.stop_event.is_set():                 # if init failed
                return
        
        success, frame =  self.cap.read()
        if not success:
            print("⚠️ Failed to grab frame")
            self.stop_event.set()                         
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
                if conf > 0.90:  # confidence > 90%
                    detected_class_ids.append(int(cls_id))
                    class_names.append(self.result.names[int(cls_id)])

        if class_names:
            print(f"Detected objects: {', '.join(set(class_names))}")
        else:
            print("⚠️ No objects detected.")

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.stop_event.set()                         # NEW
            return

        # Release resources
        
