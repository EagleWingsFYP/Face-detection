import os
import sys
import torch
import cv2
import numpy as np
from ultralytics import YOLO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.settings import debug
from navigation_plan.navigators.GridNavigator import GridNavigator

#
# The "YoloV8Tracker" class
#

class YoloV8Tracker:

    #
    # Constructor
    #

    def __init__(self, interface=None, draw_point=True, draw_boundary=True):
        
        # Arguments
        self.interface = interface
        self.draw_point = draw_point
        self.draw_boundary = draw_boundary

        # Load YOLOv8 model (ensure correct model path)
        # model_path = r"C:\Users\arees\OneDrive\Desktop\Object_Tracking_Tello\tello\drone_project\local\YoloV8Tracker_model.pt"
        # model_path = str(sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", 'local/YoloV8Tracker_model.pt'))))
        model_path = '/home/stranger/Documents/pkg/_teamup/areesha/eagle-wings-drone-project/tello/drone_project/local/YoloV8Tracker_model.pt'
        print(model_path)
        self.model = YOLO(model_path)  # Load your trained YOLOv8 model

        # Globals
        self.boundary = None
        self.center = None
        self.boundary_color = 'green'
        self.point_color = 'blue'

        # States
        self.is_tracking = False
        self.is_lost = False

        # Setup Grid Navigator
        self.navigator = GridNavigator(self)

    #
    # Core
    #

    def set_object(self):
        """ Start tracking without requiring manual bounding box input """
        self.is_tracking = True
        self.is_lost = False

    def get_object_boundary(self, frame):
        if not self.is_tracking:
            return

        # Run YOLOv8 inference on the frame
        results = self.model(frame)

        # Find the "Areesha" class in detections
        detected_face = None
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])  # Get class ID
                if class_id == 0:  # Assuming "Areesha" is class 0 in your dataset
                    detected_face = box.xyxy[0].cpu().numpy()  # Get bounding box
                    break

        if detected_face is not None:
            x1, y1, x2, y2 = map(int, detected_face)
            self.boundary = (x1, y1, x2 - x1, y2 - y1)
            self.center = ((x1 + x2) // 2, (y1 + y2) // 2)
        else:
            self.on_lost()

    def draw_object_boundary(self, frame):
        if self.is_tracking and self.boundary:
            self.interface.update_boundary(*self.boundary, color=self.boundary_color)

    def draw_center_line(self, frame):
        if self.is_tracking and self.center:
            # Draw center crosshair
            h, w, _ = frame.shape
            center_x, center_y = w // 2, h // 2
            cv2.line(frame, (center_x, 0), (center_x, h), (0, 255, 0), 1)
            cv2.line(frame, (0, center_y), (w, center_y), (0, 255, 0), 1)

            # Draw tracking line from center to detected face
            if self.center:
                cv2.line(frame, (center_x, center_y), self.center, (255, 0, 0), 2)

            self.interface.update_center(*self.center, color=self.point_color)

    def on_frame(self, frame):
        self.get_object_boundary(frame)

        if not self.is_lost:
            if self.draw_boundary:
                self.draw_object_boundary(frame)
            if self.draw_point:
                self.draw_center_line(frame)

        # Run Grid Navigator logic
        self.navigator.navigate(frame)

    #
    # Callbacks
    #

    def on_lost(self):
        """ Handle when face is lost """
        self.is_tracking = False
        self.is_lost = True
        self.boundary = None
        self.center = None
        self.interface.hide_boundary()
        self.interface.hide_center()
