import cv2
import numpy as np

class CameraError(Exception):
    """Base class for Camera-related exceptions."""
    pass

class CameraInitializationError(CameraError):
    """Raised when the camera fails to initialize."""
    pass

class FrameCaptureError(CameraError):
    """Raised when a frame cannot be captured from the camera."""
    pass

class CameraStopError(CameraError):
    """Raised when the camera fails to stop or release resources properly."""
    pass

class Camera:
    def __init__(self, source, auto_start=True):
        self.source = source
        self.cap = None
        self.is_opened = False
        if auto_start:
            self.start()

    def start(self):
        """Starts the camera and opens the video capture."""
        if not self.is_opened:
            try:
                self.cap = cv2.VideoCapture(self.source)
                if not self.cap.isOpened():
                    raise CameraInitializationError(f"Unable to open video source {self.source}")
                self.is_opened = True
            except Exception as e:
                raise CameraInitializationError(f"Failed to initialize camera: {e}")

    def frame(self):
        """Captures a single frame from the camera."""
        if self.cap is None or not self.cap.isOpened():
            raise FrameCaptureError("Camera not initialized or is already closed.")
        
        ret, frame = self.cap.read()
        if not ret:
            raise FrameCaptureError("Failed to capture frame.")
        
        return frame

    def stop(self):
        """Stops the camera and releases resources."""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False

    def __del__(self):
        self.stop()
        
    def get_frame(self):
        """
        Captures a frame and encodes it as JPEG bytes for HTTP streaming.
        """
        frame = self.frame()
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            raise FrameCaptureError("Failed to encode frame to JPEG.")
        return buffer.tobytes()
