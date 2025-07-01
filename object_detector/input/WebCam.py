import cv2
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from core.Camera import Camera

class WebCam(Camera):
    def __init__(self, source=0, auto_start=True):
        """
        WebCam uses the default source 0 (webcam) unless otherwise specified.
        """
        super().__init__(source, auto_start)
