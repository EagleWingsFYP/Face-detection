from djitellopy import Tello
import numpy as np
import cv2

class TelloCam:
    def __init__(self, tello: Tello):
        try:
            self.frame_read = tello.get_frame_read()
        except:
            self.frame_read = None

    def frame(self):
        frame = np.zeros((720, 960, 3), dtype=np.uint8)
        try:
            frame = self.frame_read.frame

            # frame = cv2.resize(frame, (640, 480))
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                print("None")
        except:
            pass

        return frame
