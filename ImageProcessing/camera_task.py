from ultralytics import YOLO
import cv2


class CameraTask:
    def __init__(self):
        self._inited = False

    def _init_hw(self):

        # Load the YOLOv5 model
        self.model = YOLO('yolov5s.pt')  # Replace with custome model 'yolov5n.pt' once completed

        #Open webcam (0 = default camera) needs to be updated for the on board camera not laptop webcame
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            print("Cannot open camera")
            exit()

        print("Starting webcam detection... Press 'q' to quit.")
        # Processing video frames in a loop
    def step(self):
                
        if not self._inited:
            self._init_hw()
        
        success, frame =  self.cap.read()
        if not success:
            print("⚠️ Failed to grab frame")
            exit()

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
            print(f"✅ Detected objects: {', '.join(set(class_names))}")
        else:
            print("⚠️ No objects detected.")

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            exit()

        # Release resources
        self.cap.release()
        cv2.destroyAllWindows()
