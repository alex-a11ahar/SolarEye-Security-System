import cv2
import numpy as np

# Load YOLO pre-trained model and class names
net = cv2.dnn.readNetFromDarknet('yolov4.cfg', 'yolov4-tiny.weights')
layer_names = net.getLayerNames()

# Correct the output layers indexing (subtract 1 from each layer index returned by getUnconnectedOutLayers)
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]

# Load class names (e.g., person, car, etc.)
with open('coco.names', 'r') as f:
    classes = [line.strip() for line in f.readlines()]

# Initialize video capture (use 0 for the default camera)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Prepare the frame for YOLO (resize and normalize)
    blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)

    # Analyze the detected objects in the frame
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]

            if confidence > 0.5:  # Adjust threshold as needed
                # Get object label and draw bounding box
                label = classes[class_id]
                print(f"Detected: {label} with confidence: {confidence}")

                # Get the bounding box coordinates
                center_x = int(detection[0] * frame.shape[1])
                center_y = int(detection[1] * frame.shape[0])
                w = int(detection[2] * frame.shape[1])
                h = int(detection[3] * frame.shape[0])

                # Draw a rectangle around the object
                cv2.rectangle(frame, (center_x, center_y), (center_x + w, center_y + h), (0, 255, 0), 2)
                cv2.putText(frame, label, (center_x, center_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Display the frame with detected objects
    # cv2.imshow('YOLO Object Detection', frame)

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
