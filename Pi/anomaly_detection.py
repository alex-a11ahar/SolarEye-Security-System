import cv2
import os
import numpy as np
from pathlib import Path

# Function to calculate optical flow between two frames
def calculate_optical_flow(prev_frame, next_frame):
    # Convert frames to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    next_gray = cv2.cvtColor(next_frame, cv2.COLOR_BGR2GRAY)

    # Calculate optical flow using Farneback method
    flow = cv2.calcOpticalFlowFarneback(prev_gray, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return magnitude

# Function to detect anomalies based on optical flow
def detect_anomaly(optical_flow, mean_flow, stddev_flow, threshold=3):
    # Calculate the difference from the mean
    diff = np.abs(optical_flow - mean_flow)
    # Check if the difference exceeds the threshold (in terms of standard deviations)
    return np.any(diff > (threshold * stddev_flow))

# Directory setup
frames_dir = Path("preprocessed_frames")  # Specify the directory with preprocessed frames
output_dir = Path("anomaly_frames")  # Directory to save frames with detected anomalies
output_dir.mkdir(parents=True, exist_ok=True)  # Create directory for anomaly frames

# List all preprocessed frame files in the directory
frame_files = sorted(frames_dir.glob("*.jpg"))  # Ensure the frames are sorted
max_frames = min(len(frame_files), 250)  # Limit to 250 frames

print(f"Processing {max_frames} frames from {frames_dir}")

# Load frames into an array for optical flow calculation
frames_array = []
for frame_num in range(max_frames):
    frame_filename = frame_files[frame_num]
    frame = cv2.imread(str(frame_filename))
    frames_array.append(frame)

# Convert the list to a numpy array
frames_array = np.array(frames_array)

# Calculate optical flow for the frames
optical_flows = []
for i in range(1, len(frames_array)):
    flow = calculate_optical_flow(frames_array[i - 1], frames_array[i])
    optical_flows.append(flow.flatten())  # Flatten the flow magnitude for processing

# Convert optical flows to a numpy array
optical_flows = np.array(optical_flows)

# Calculate mean and standard deviation of the optical flows
mean_flow = np.mean(optical_flows, axis=0)
stddev_flow = np.std(optical_flows, axis=0)

# Analyze each frame for anomalies based on the optical flow
for frame_num in range(1, max_frames):  # Start from 1 since we compare with the previous frame
    frame_filename = frame_files[frame_num]
    frame = cv2.imread(str(frame_filename))
    
    # Get the optical flow for the current frame
    current_flow = calculate_optical_flow(frames_array[frame_num - 1], frames_array[frame_num]).flatten()

    # Run anomaly detection
    is_anomaly = detect_anomaly(current_flow, mean_flow, stddev_flow)

    if is_anomaly:
        print(f"Anomaly detected in frame {frame_num} ({frame_filename.name})")
        # Save frame with anomaly
        anomaly_frame_filename = output_dir / f"anomaly_frame_{frame_num:05d}.jpg"
        cv2.imwrite(str(anomaly_frame_filename), frame)  # Save frame with anomaly

print("Processing complete.")
