import cv2
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from navigation_plan.util.draw_grid_3x3 import draw_grid_3x3, highlight_cell
from config.settings import GRID_CENTER, SAFE_DISTANCE

class GridGuide:

    def __init__(self, navigator, controller, show_grid=True, show_direction=True, show=True, enable=True):

        # Arguments
        self.navigator = navigator
        self.controller = controller
        self.show_direction = show_direction
        self.show_grid = show_grid
        self.show = show
        self.enabled = enable

        # State
        self.is_static = True

        # Variables
        self.direction = {'x_axis': 0, 'y_axis': 0, 'z_axis': 0}
        self.cell = (1, 1)

    # 
    # Core
    # 

    def calculate_direction(self):
        if not self.navigator.ready:
            return

        # Loop through each axis and zero out if within safe limits
        for axis, safe_limit in zip(['x_axis', 'y_axis', 'z_axis'], [GRID_CENTER[0] / 2, GRID_CENTER[1] / 2, SAFE_DISTANCE]):
            distance = self.navigator.location[axis]
            self.direction[axis] = 0 if abs(distance) < safe_limit else distance


    def update_grid(self, frame):

        if not self.navigator.ready: return

        self.calculate_direction()

        cell_idx = lambda v: 2 if v > 0 else (0 if v < 0 else 1)

        self.cell = (
            cell_idx(-self.direction['y_axis']),
            cell_idx(self.direction['x_axis']),
        )

        if self.show:
            if self.show_grid:                              draw_grid_3x3(frame, GRID_CENTER)
            if self.show_direction and self.cell != (1, 1): highlight_cell(frame, self.cell, GRID_CENTER)

    # 
    # The "loop"
    # 

    def loop(self):
        if not self.enabled:
            return

        self.calculate_direction()
        
        # Check if any direction is non-zero and move if true
        if any(self.direction.values()):
            self.is_static = False
            # print("D", self.direction)
            self.controller.move(**self.direction)

        else:
            # print("STATIC")
            if not self.is_static:
                self.is_static = True
                self.controller.stop(True)
