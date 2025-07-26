from djitellopy import Tello
import numpy as np
import cv2
import time

class TelloCam:
    def __init__(self, tello: Tello):
        self.tello = tello
        self.frame_read = None
        self.is_connected = True
        self.last_frame_time = time.time()
        self.connection_timeout = 5.0  # 5 seconds timeout
        
        try:
            self.frame_read = tello.get_frame_read()
            print("[TelloCam] Successfully initialized frame reader")
        except Exception as e:
            print(f"[TelloCam] Failed to initialize frame reader: {e}")
            self.frame_read = None
            self.is_connected = False

    def frame(self):
        frame = np.zeros((720, 960, 3), dtype=np.uint8)
        
        # Check if we're still connected
        if not self.is_connected:
            return frame
            
        try:
            # Check for connection timeout
            current_time = time.time()
            if current_time - self.last_frame_time > self.connection_timeout:
                print("[TelloCam] Connection timeout detected")
                self.is_connected = False
                return frame
            
            if self.frame_read is None:
                return frame
                
            frame = self.frame_read.frame
            
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.last_frame_time = current_time  # Update last successful frame time
            else:
                print("[TelloCam] Received None frame")
                # Check if we should mark as disconnected
                if current_time - self.last_frame_time > 2.0:  # 2 seconds without valid frame
                    print("[TelloCam] No valid frames received, marking as disconnected")
                    self.is_connected = False
                    
        except Exception as e:
            print(f"[TelloCam] Error getting frame: {e}")
            self.is_connected = False

        return frame

    def stop(self):
        """Gracefully stop the TelloCam and release resources."""
        print("[TelloCam] Stopping TelloCam...")
        self.is_connected = False
        
        try:
            if self.tello is not None:
                # Only try to stop stream if we're actually connected
                try:
                    # Check if tello is still responsive
                    if hasattr(self.tello, '_connected') and self.tello._connected:
                        print("[TelloCam] Stopping Tello stream...")
                        self.tello.streamoff()
                except Exception as e:
                    print(f"[TelloCam] Error stopping stream: {e}")
                    # Don't raise - this is expected when drone is disconnected
        except Exception as e:
            print(f"[TelloCam] Error in stop(): {e}")
        
        self.frame_read = None
        print("[TelloCam] TelloCam stopped successfully")

    def is_connected(self):
        """Check if the TelloCam is still connected."""
        return self.is_connected

    def check_connection(self):
        """Check if the drone is still connected by testing a simple command."""
        if self.tello is None:
            return False
            
        try:
            # Try to get battery level as a connection test
            if hasattr(self.tello, 'get_battery'):
                battery = self.tello.get_battery()
                if battery > 0:
                    return True
                else:
                    print("[TelloCam] Battery test failed - drone disconnected")
                    return False
        except Exception as e:
            print(f"[TelloCam] Connection test failed: {e}")
            return False
        
        return False
