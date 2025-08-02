import cv2
import numpy as np
import os
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from light_cnn import LightCNN_29Layers
from scipy.spatial.distance import cosine
import pickle
import time
from navigation_plan.navigators.GridNavigator import GridNavigator

model = LightCNN_29Layers(num_classes=79077)
checkpoint = torch.load('F:\EagleWingsSystem\EagleWings\modules\faceDetection\object_detector\LightCNN_29Layers_checkpoint.pth_2', map_location=torch.device('cpu'))
state_dict = checkpoint['state_dict']
state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
model.load_state_dict(state_dict)
model.eval()

feature_db = {}  # {person_name: [feature_vectors]}
feature_dir = 'drone_project/data/extracted_features/'

for folder in os.listdir(feature_dir):
    person_dir = os.path.join(feature_dir, folder)
    if os.path.isdir(person_dir):
        feature_db[folder] = []
        for file in os.listdir(person_dir):
            if file.endswith('.feat'):
                with open(os.path.join(person_dir, file), 'rb') as f:
                    feature = pickle.load(f)
                    feature_db[folder].append(feature)

transform = transforms.Compose([transforms.ToTensor()])

def extract_face_features(img):
    """Extract features from a single face."""
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.resize(img, (128, 128))
    img_tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        features = model(img_tensor)
    return features[1].data.cpu().numpy()[0]

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

class FaceTracker:
    def __init__(self, draw_point=True, draw_boundary=True):
        self.draw_point = draw_point
        self.draw_boundary = draw_boundary
        self.boundary = None
        self.center = None
        self.is_tracking = False
        self.is_lost = False
        self.navigator = GridNavigator(self)

    def recognize_face(self, frame):
        """Recognize faces and track movement."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) == 0:
            self.on_lost()
            return frame

        features_list = []
        face_coords = []

        for (x, y, w, h) in faces:
            face = frame[y:y+h, x:x+w]
            features = extract_face_features(face)
            features_list.append(features)
            face_coords.append((x, y, w, h))

        best_matches = []
        for features in features_list:
            best_match = "Unknown"
            best_similarity = float('inf')

            for person_name, db_features in feature_db.items():
                for db_feature in db_features:
                    similarity = cosine(features, db_feature)
                    if similarity < best_similarity:
                        best_similarity = similarity
                        best_match = person_name

            if best_similarity >= 0.7:
                best_match = "Unknown"

            best_matches.append(best_match)

        self.is_tracking = True
        self.is_lost = False

        for i, (x, y, w, h) in enumerate(face_coords):
            label = best_matches[i]
            self.boundary = (x, y, w, h)
            self.center = (x + w // 2, y + h // 2)

            if self.draw_boundary:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            if self.draw_point:
                h, w, _ = frame.shape
                center_x, center_y = w // 2, h // 2
                cv2.line(frame, (center_x, 0), (center_x, h), (0, 255, 0), 1)
                cv2.line(frame, (0, center_y), (w, center_y), (0, 255, 0), 1)
                cv2.line(frame, (center_x, center_y), self.center, (255, 0, 0), 2)

        self.navigator.navigate(frame)
        return frame

    def on_lost(self):
        """Handle when the face is lost."""
        self.is_tracking = False
        self.is_lost = True
        self.boundary = None
        self.center = None

tracker = FaceTracker()
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    start_time = time.time()
    frame = tracker.recognize_face(frame)
    end_time = time.time()

    cv2.imshow('Face Tracking', frame)

    fps = 1 / (end_time - start_time)
    print(f"FPS: {fps:.2f}")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
