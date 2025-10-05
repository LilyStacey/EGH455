import cv2
from ultralytics import YOLO

# 1. Load the YOLOv5 model
model = YOLO('yolov5s.pt')  # You can also use 'yolov5n.pt' or your custom model

# 2. Open webcam (0 = default camera)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Cannot open camera")
    exit()

print("🎥 Starting webcam detection... Press 'q' to quit.")

# 3. Process video frames in a loop
while True:
    success, frame = cap.read()
    if not success:
        print("⚠️ Failed to grab frame")
        break

    # 4. Run inference on the frame (as a numpy array)
    results = model(frame, verbose=False)
    result = results[0]

    # 5. Visualize detections on frame
    annotated_frame = result.plot()

    # 6. Show frame in window
    cv2.imshow("YOLOv5 Live", annotated_frame)

    # detected_class_ids = result.boxes.cls.tolist() if result.boxes else []

    # class_names = [result.names[int(cls_id)] for cls_id in detected_class_ids]

    detected_class_ids = []
    class_names = []

    # Check if there are any detected boxes
    if result.boxes:
        for cls_id, conf in zip(result.boxes.cls, result.boxes.conf):
            if conf > 0.90:  # confidence > 90%
                detected_class_ids.append(int(cls_id))
                class_names.append(result.names[int(cls_id)])

    if class_names:
        print(f"✅ Detected objects: {', '.join(set(class_names))}")
    else:
        print("⚠️ No objects detected.")

    # 7. Break on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 8. Release resources
cap.release()
cv2.destroyAllWindows()
