import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import cv2
from config.settings import debug


# 
# The "CSRTTracker" class
# 

class CSRTTracker:

    # 
    # Constructor
    # 

    def __init__(self, interface=None, draw_point=True, draw_boundary=True):
        
        # Arguments
        self.interface = interface
        self.draw_point = draw_point
        self.draw_boundary = draw_boundary

        # Globals
        self.boundary = None
        self.center = False
        self.boundary_color = 'green'
        self.point_color = 'blue'

        # States
        self.is_tracking = False
        self.is_lost = False

        # Setup
        self.initialize_tracker()

    def initialize_tracker(self):
        self.tracker = cv2.TrackerCSRT_create()
        self.is_tracking = False

    # 
    # Core
    # 

    def set_object(self):
        self.boundary = self.interface.boundary
        self.tracker.init(self.interface.boundary_frame, tuple(self.boundary))
        self.is_tracking = True
        self.is_lost = False

        if self.draw_boundary: self.interface.show_boundary()
        if self.draw_point: self.interface.show_center()

    def get_object_boundary(self, frame):
        if self.is_tracking:
            success, bbox = self.tracker.update(frame)
            if success:
                self.boundary = tuple(map(int, bbox))
                x, y, w, h = self.boundary
                self.center = (x + w // 2, y + h // 2)
            else:
                self.on_lost()
                if debug: print("[DBG] CSRT Tracking lost.")

    def draw_object_boundary(self, frame):
        if self.is_tracking and self.boundary:            
            if self.boundary:
                self.interface.update_boundary(*self.boundary, color=self.boundary_color)

    def draw_center_line(self, frame):
        if self.is_tracking and self.center:
            self.interface.update_center(*self.center, color=self.point_color)

    def on_frame(self, frame):
        self.get_object_boundary(frame)

        if not self.is_lost:
            if self.draw_boundary: self.draw_object_boundary(frame)
            if self.draw_point: self.draw_center_line(frame)
    
    # 
    # Callbacks
    # 

    def on_lost(self):
        self.is_tracking = False
        self.is_lost = True
        self.boundary = None
        self.center = False
        self.interface.hide_boundary()
        self.interface.hide_center()
