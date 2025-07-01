import random
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.settings import debug
from .DaSiamRPNTracker import DaSiamRPNTracker

class DaSiamMultipleTracker:

    # 
    # Constructor
    # 

    def __init__(self, interface, draw_point=True, draw_boundary=True):

        # Arguments
        self.interface = interface
        self.draw_point = draw_point
        self.draw_boundary = draw_boundary

        # Config
        self.number_of_models = 2
        self.distance_threshold = 90

        # States
        self.is_tracking = False
        self.is_lost = False
        self.lost_count = 0

        # Globals
        self.models = [DaSiamRPNTracker(interface, draw_point, draw_boundary, as_submodel=True)] * self.number_of_models
        self.center = False
        self.boundary = None
        self.model_index = 0
        self.lost_set = set()
        self.boundaries = []
        self.boundary_color = 'green'
        self.point_color = 'blue'

    # 
    # Core
    # 

    def set_object(self):

        # Get Actual Boundary
        x, y, w, h = self.interface.boundary

        # Gen Boundary Copies
        boundaries = [
            [x, y, w, h],       # actual
            [x-25, y+25, w, h], # cupy: up-left
            [x+25, y+25, w, h], # cupy: up-right
            [x-25, y-25, w, h], # cupy: low-left
            [x+25, y-25, w, h], # cupy: low-right
        ]
        if self.number_of_models > 5:
            for _ in range(5, self.number_of_models):
                offset_x = random.randint(-30, 30)
                offset_y = random.randint(-30, 30)
                boundaries.append([x + offset_x, y + offset_y, w, h])

        # Initialize Models
        for i, model in enumerate(self.models):
            model.set_object(boundaries[i])

        self.is_tracking = True
        self.is_lost = False

        if self.draw_boundary:
            if self.boundary:
                self.interface.update_boundary(*self.boundary, color=self.boundary_color)
            self.interface.show_boundary()

        if self.draw_point:
            if self.center:
                self.interface.update_center(*self.center, color=self.boundary_color)
            self.interface.show_center()

    def check_lost(self):
        if self.is_lost:
            for model in self.models:
                model.boundary = None
                model.center = None
                model.initialize_tracker()


    def get_object_boundary(self, frame):

        self.lost_count = 0
        self.model_index = 0
        self.lost_set.clear()
        
        if self.is_tracking:
            for i, model in enumerate(self.models):
                model.get_object_boundary(frame)
                boundary = model.boundary

                # to see how many lost due to crossing frame boundary
                if not boundary:
                    self.lost_set.add(i)
                    self.lost_count += 1
                    if self.model_index == i:
                        self.model_index += 1
                else:
                    self.boundaries.append((i, boundary))
                    self.lost_set.discard(i)

            # to see how many are outliers
            self.check_too_far()
            if self.lost_count > 0:
                if debug: print("[DBG] lost count", self.lost_count)
                if debug: print(("[DBG] these are lost"), [i for i in self.lost_set])
            if self.model_index >= self.number_of_models:
                self.lost_count = 3
            if self.lost_count >= 3:
                self.on_lost()
            else:
                self.boundary = self.models[self.model_index].boundary
                x, y, w, h = self.boundary
                self.center = (int(x + w / 2), int(y + h / 2))
            
            self.check_lost()
        
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


    # 
    # Util
    # 

    def check_too_far(self):
        centers = {}
        for i, (x, y, w, h) in self.boundaries:
            center_x = x + w/2
            center_y = y + h/2
            centers[i] = (center_x, center_y)
        
        for i, center1 in centers.items():
            far_points = 0
            for j, center2 in centers.items():
                if i != j:
                    distance = ((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)**0.5
                    if distance > self.distance_threshold:
                        far_points += 1
            
            # If point is far from at least 2 others
            if far_points >= 2:
                self.lost_set.add(i)
                self.lost_count += 1
                print("[DBG] lost due to distance from 2 others")
            else:
                self.lost_set.discard(i)
