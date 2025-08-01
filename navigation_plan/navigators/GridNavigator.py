
import cv2
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..//")))
from config.settings import FRAME_SIZE, MAX_DISTANCE, GRID_CENTER, debug


class GridNavigatorError(Exception): pass
class PointModelExpectedError(GridNavigatorError): pass
class InvalidCenterValue(GridNavigatorError): pass


class GridNavigator:


    def __init__(self, model, enabled=True):
        
        self.model = model
        self.enabled = enabled

        self.x_limit = FRAME_SIZE[0] // 2
        self.y_limit = FRAME_SIZE[1] // 2
        self.z_limit = MAX_DISTANCE
        self.DISTANCE_THRESHOLD = 5
        self.grid_center_area = GRID_CENTER[0] * GRID_CENTER[1]
        
        self.location = {'x_axis': 0, 'y_axis': 0, 'z_axis': 0}
        self.ready = False

    
    def calculate_location(self, frame):
        
        if self.model.center is None:
            self.location = {'x_axis': 0, 'y_axis': 0, 'z_axis': 0}
            return
        elif not isinstance(self.model.center, tuple) or len(self.model.center) != 2:
            self.location = {'x_axis': 0, 'y_axis': 0, 'z_axis': 0}
            return

        frame_height, frame_width = frame.shape[:2]
        frame_center = (frame_width // 2, frame_height // 2)
        diff_x = self.model.center[0] - frame_center[0]
        diff_y = self.model.center[1] - frame_center[1]

        self.location['x_axis'] = max(-self.x_limit, min(self.x_limit, diff_x))
        self.location['y_axis'] = -max(-self.y_limit, min(self.y_limit, diff_y))

        if self.model.boundary is not None:
            area = self.model.boundary[2] * self.model.boundary[3]
            target_area = self.grid_center_area / self.DISTANCE_THRESHOLD
            z_value = (area - target_area) / (target_area / MAX_DISTANCE)
            self.location['z_axis'] = -max(-self.z_limit, min(self.z_limit, z_value))

        self.ready = True


    def navigate(self, frame):

        if not self.enabled: return
        self.calculate_location(frame)
        
