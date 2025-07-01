import sys, time
from os.path import join, dirname, abspath
sys.path.append(abspath(join(dirname(__file__), "../../")))
sys.path.append(abspath(join(dirname(__file__), "../../lib/dasiamrpn/")))

import torch
import numpy as np
from net import SiamRPNvot
from run_SiamRPN import SiamRPN_init, SiamRPN_track

from config.settings import debug

class DaSiamRPNTracker:

    # 
    # Config
    # 
    MODEL_FILE = './dist/SiamRPNOTB.model'
    BORDER_THRESHOLD = 5
    LOST_TIMEOUT = 1.5

    # 
    # Constructor
    # 

    def __init__(self, interface, draw_boundary=True, draw_point=True, as_submodel=False):
        # Arguments
        self.interface = interface
        self.draw_boundary = draw_boundary
        self.draw_point = draw_point
        self.as_submodel = as_submodel

        # Config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # State
        self.is_tracking = False
        self.is_lost = False

        # Globals
        self.model = None
        self.target = None
        self.boundary = None
        self.center = False
        self.border_crossed_at = None

        # Colors
        self.boundary_color = 'green'
        self.point_color = 'blue'

        # Setup
        self.initialize_tracker()

    def initialize_tracker(self):
        
        self.model = SiamRPNvot()
        self.model.load_state_dict(torch.load(self.MODEL_FILE, map_location=self.device))  # Load model on selected device
        self.model.to(self.device)
        self.model.eval()


    # 
    # Core
    # 

    def set_object(self, boundary=None):

        self.boundary = boundary if boundary else self.interface.boundary
        frame = self.interface.boundary_frame

        self.is_tracking = True
        self.is_lost = False

        # Boundary and center to initialize
        x, y, w, h = self.boundary
        cx, cy = x + w / 2, y + h / 2
        target_pos, target_sz = np.array([cx, cy]), np.array([w, h])

        # Initialize Target
        self.target = SiamRPN_init(frame, target_pos, target_sz, self.model, self.device)

        if not self.as_submodel:
            if self.draw_boundary: self.interface.show_boundary()
            if self.draw_point: self.interface.show_center()


    def get_object_boundary(self, frame):
        if self.is_tracking:
            self.target = SiamRPN_track(self.target, frame, self.device)

            cx, cy = self.target['target_pos']
            w, h = self.target['target_sz']
            x, y = cx - w / 2, cy - h / 2

            self.boundary = tuple(int(l) for l in (x, y, w, h))
            self.center = tuple(int(l) for l in (cx, cy))

            if self.lost(frame): self.on_lost()

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
    # Helpers
    # 

    def lost(self, frame):

        def target_crossed_border():
            x, y, w, h = self.boundary
            frame_height, frame_width = frame.shape[:2]
            return x<self.BORDER_THRESHOLD or y<self.BORDER_THRESHOLD or x+w>frame_width-self.BORDER_THRESHOLD or y+h>frame_height-self.BORDER_THRESHOLD

        if target_crossed_border():
            if debug: print("[DBG] a bbox just overflown the frame")

            if self.border_crossed_at is None:
                self.border_crossed_at = time.time()
            
            elif time.time() - self.border_crossed_at >= self.LOST_TIMEOUT:
                if debug: print(f"[DBG] a bbox is overflowing the frame for {self.LOST_TIMEOUT} seconds (lost)")
                return True
        
        else: self.border_crossed_at = None
        
        return False

    # 
    # Callbacks
    # 

    def on_lost(self):
        self.is_tracking = False
        self.is_lost = True
        self.boundary = None
        self.center = False

        if not self.as_submodel:
            self.interface.hide_boundary()
            self.interface.hide_center()
