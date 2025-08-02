import cv2
import numpy as np
import os
import torch
import torchvision.transforms as transforms
from .light_cnn import LightCNN_29Layers
from scipy.spatial.distance import cosine
import pickle
from navigation_plan.navigators.GridNavigator import GridNavigator
from PyQt6.QtCore import QObject, pyqtSignal
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../database')))
class LightCNNTracker(QObject):
    boundaryUpdated = pyqtSignal(tuple)  # Emits (x, y, w, h)
    centerUpdated = pyqtSignal(tuple)    # Emits (x_center, y_center)
    trackingLost = pyqtSignal()          # Emits when tracking is lost

    def __init__(self, interface=None, 
                 model_path=os.path.join(os.path.dirname(__file__), '..', 'LightCNN_29Layers_checkpoint.pth_2'), 
                 feature_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../database/extracted_features')),
                 similarity_threshold=0.7):
        """
        Initialize the LightCNNTracker.
        Loads the pre-trained LightCNN model, feature database,
        sets up preprocessing, and initializes tracking state.
        """
        super().__init__()
        self.interface = interface
        self.similarity_threshold = similarity_threshold

        self.model = LightCNN_29Layers(num_classes=79077)
        checkpoint = torch.load(model_path, map_location=torch.device('cpu'))
        state_dict = checkpoint['state_dict']
        state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
        self.model.load_state_dict(state_dict)
        self.model.eval()

        self.feature_db = {}
        for folder in os.listdir(feature_dir):
            person_dir = os.path.join(feature_dir, folder)
            if os.path.isdir(person_dir):
                self.feature_db[folder] = []
                for file in os.listdir(person_dir):
                    if file.endswith('.feat'):
                        with open(os.path.join(person_dir, file), 'rb') as f:
                            feature = pickle.load(f)
                            self.feature_db[folder].append(feature)

        self.transform = transforms.Compose([transforms.ToTensor()])
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        self.boundary = None  # (x, y, w, h)
        self.center = None    # (x_center, y_center)
        self.is_tracking = False

        self.detections = []

        self.navigator = GridNavigator(self) if self.interface else None 

    def set_object(self):
        """Start tracking using the current boundary and center."""
        self.is_tracking = True

    def extract_face_features(self, img):
        """
        Preprocess the face image and extract features using the LightCNN model.
        Returns a feature vector.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128))
        img_tensor = self.transform(resized).unsqueeze(0)  # Add batch dimension
        with torch.no_grad():
            features = self.model(img_tensor)
        return features[1].data.cpu().numpy()[0]

    def recognize_face(self, frame):
        """
        Detect faces in the frame using Haar cascades, extract features,
        compare against the feature database, and annotate the frame.
        Auto-select if only one face is detected.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        self.detections = []  # Clear previous detections

        if len(faces) == 0:
            self.on_lost()
            return frame

        for (x, y, w, h) in faces:
            face_img = frame[y:y+h, x:x+w]
            features = self.extract_face_features(face_img)
            
            best_match = "Unknown"
            best_similarity = float('inf')
            for person_name, db_features in self.feature_db.items():
                for db_feat in db_features:
                    similarity = cosine(features, db_feat)
                    if similarity < best_similarity:
                        best_similarity = similarity
                        best_match = person_name

            if best_similarity >= self.similarity_threshold:
                best_match = "Unknown"

            print(f"Detected {best_match} with similarity {best_similarity:.3f}")

            detection = {
                "box": (x, y, w, h),
                "center": (x + w // 2, y + h // 2),
                "label": best_match,
                "similarity": best_similarity
            }
            self.detections.append(detection)

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, best_match, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        if len(self.detections) == 1:
            sel = self.detections[0]
            self.boundary = sel["box"]
            self.center = sel["center"]
            self.is_tracking = True
            if self.interface:
                self.boundaryUpdated.emit(self.boundary)
                self.centerUpdated.emit(self.center)
        
        return frame

    def select_face(self, click_x, click_y):
        """
        When a click is detected, check if the click falls within a detection's box.
        If so, select that face for tracking and emit UI update signals.
        """
        for detection in self.detections:
            x, y, w, h = detection["box"]
            if x <= click_x <= x + w and y <= click_y <= y + h:
                self.boundary = detection["box"]
                self.center = detection["center"]
                self.is_tracking = True
                self.boundaryUpdated.emit(self.boundary)
                self.centerUpdated.emit(self.center)
                print(f"Selected face: {detection['label']} with similarity {detection['similarity']:.3f}")
                return detection
        print("No face selected on click.")
        return None

    def on_lost(self):
        """Handle the loss of tracking by resetting the state and emitting a signal."""
        self.is_tracking = False
        self.boundary = None
        self.center = None
        if self.interface:
            self.trackingLost.emit()

    def on_frame(self, frame):
        """
        Process each frame:
          - Recognize and annotate faces.
          - Draw visual aids if tracking is active.
          - Call the navigator to adjust movement.
        Returns the processed frame.
        """
        frame = self.recognize_face(frame)
        
        if self.is_tracking and self.center is not None:
            frame_h, frame_w = frame.shape[:2]
            frame_center = (frame_w // 2, frame_h // 2)
            cv2.line(frame, (frame_center[0], 0), (frame_center[0], frame_h), (0, 255, 0), 1)
            cv2.line(frame, (0, frame_center[1]), (frame_w, frame_center[1]), (0, 255, 0), 1)
            cv2.line(frame, frame_center, self.center, (255, 0, 0), 2)
        
        if self.navigator:
            self.navigator.navigate(frame)
        return frame
