import cv2
import numpy as np
import os
import torch
import torchvision.transforms as transforms
from light_cnn import LightCNN_29Layers
from scipy.spatial.distance import cosine
import pickle
import time
import threading
from queue import Queue

# Load pre-trained model (LightCNN)
device = torch.device('cpu')  # Force CPU usage
model = LightCNN_29Layers(num_classes=79077).to(device)
checkpoint = torch.load('F:\Python Project\LightCNN\LightCNN_29Layers_V2_checkpoint.pth', map_location=device)
state_dict = checkpoint['state_dict']
state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
model.load_state_dict(state_dict)
model.eval()

# Load feature database (features and labels)
feature_db = {}  # {person_name: [feature_vectors]}
feature_dir = 'D:/Drone/LightCNN/extracted_features/'

# Read all .feat files and load features
for folder in os.listdir(feature_dir):
    person_dir = os.path.join(feature_dir, folder)
    if os.path.isdir(person_dir):
        feature_db[folder] = []
        for file in os.listdir(person_dir):
            if file.endswith('.feat'):
                with open(os.path.join(person_dir, file), 'rb') as f:
                    feature = pickle.load(f)
                    feature_db[folder].append(feature)

# Preprocessing function
transform = transforms.Compose([transforms.ToTensor()])

def extract_face_features(img):
    """Extract features from a single face."""
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
    img = cv2.resize(img, (128, 128))  # Resize to 128x128
    img_tensor = transform(img).unsqueeze(0).to(device)  # Add batch dimension
    with torch.no_grad():  # Disable gradients for inference
        features = model(img_tensor)
    return features[1].data.numpy()[0]

# Face detection using Haar Cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def recognize_face(frame):
    """Recognize faces in a given frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    if len(faces) == 0:
        return frame

    features_list = []
    face_coords = []

    # Extract features for each detected face in the frame
    for (x, y, w, h) in faces:
        face = frame[y:y+h, x:x+w]
        features = extract_face_features(face)
        features_list.append(features)
        face_coords.append((x, y, w, h))

    # Compare features with the database (batch comparison)
    best_matches = []
    for features in features_list:
        best_match = "Unknown"
        best_similarity = float('inf')

        # Efficient comparison using cosine similarity
        for person_name, db_features in feature_db.items():
            for db_feature in db_features:
                similarity = cosine(features, db_feature)
                if similarity < best_similarity:
                    best_similarity = similarity
                    best_match = person_name

        # If the best match similarity is above a threshold, consider it "Unknown"
        if best_similarity >= 0.7:  # Adjust this threshold based on accuracy needs
            best_match = "Unknown"

        best_matches.append(best_match)

    # Annotate the frame with results
    for i, (x, y, w, h) in enumerate(face_coords):
        label = best_matches[i]
        cv2.putText(frame, f'{label}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    return frame

# Threaded frame processing
frame_queue = Queue(maxsize=2)
result_queue = Queue(maxsize=2)

def process_frames():
    while True:
        frame = frame_queue.get()
        result_frame = recognize_face(frame)
        result_queue.put(result_frame)


def display_frames():
    while True:
        result_frame = result_queue.get()
        cv2.imshow('Face Recognition', result_frame)

# Start threads
processing_thread = threading.Thread(target=process_frames, daemon=True)
processing_thread.start()

display_thread = threading.Thread(target=display_frames, daemon=True)
display_thread.start()

# Use your phone's IP camera stream
phone_camera_url = 'http://192.168.0.104:4747/video'
cap = cv2.VideoCapture(phone_camera_url)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame. Check the IP camera stream URL.")
        break

    # Add the frame to the processing queue
    if not frame_queue.full():
        frame_queue.put(frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):  # Press 'q' to exit
        break

cap.release()
cv2.destroyAllWindows()
