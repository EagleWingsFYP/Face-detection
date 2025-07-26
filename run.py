import sys, os, time

from dotenv import load_dotenv

# Add the tello module to sys.path if not already present
tello_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tello'))
if tello_path not in sys.path:
    sys.path.insert(0, tello_path)

# Add the EagleWings root to sys.path for module imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

interface_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../interface'))
if interface_path not in sys.path:
    sys.path.insert(0, interface_path)

from modules.models.attack import execute_attack
from config.settings import debug
#  
# Environment
# 

load_dotenv()

# Set defaults – note that LightCNNTracker is now prioritized.
DEFAULT_CAMERA    = "WebCam"
DEFAULT_INTERFACE = "CV2Interface"
DEFAULT_MODEL     = "DaSiamRPNTracker"  

camera_type    = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CAMERA",    DEFAULT_CAMERA   )
interface_type = sys.argv[2] if len(sys.argv) > 2 else os.getenv("INTERFACE", DEFAULT_INTERFACE)
model_type     = sys.argv[3] if len(sys.argv) > 3 else os.getenv("MODEL",     DEFAULT_MODEL    )

#  
# Globals
# 

tello = None
app = None
camera = None
controller = None
interface = None
model = None
navigator = None
guide = None

#  
# Instances Setup
# 

# Tello
def setup_tello():
    global tello, camera  # <== Fix here

    if camera_type == "TelloCam":
        if tello is None:
            print("❌ [run.py] Tello is None. Cannot initialize TelloCam.")
            return
        elif hasattr(tello, '_connected') and not tello._connected:
            print("❌ [run.py] Dummy Tello is not connected. Cannot initialize TelloCam.")
            return
        else:
            print("✅ [run.py] Tello is set and connected. Initializing TelloCam...")

        from object_detector.input.TelloCam import TelloCam
        camera = TelloCam(tello)  # now this assigns globally
        return

    print("[INFO] Tello not required!")

def tello_shutdown():
    global tello

    if tello and int(os.getenv("AUTO_STREAMON", True)):
        print("Shutdown Sequence _/!\\_")
        try:
            # Only try to stop stream if we're actually connected
            if hasattr(tello, '_connected') and tello._connected:
                print("[run.py] Stopping Tello stream during shutdown...")
                tello.streamoff()
            else:
                print("[run.py] Tello not connected, skipping streamoff")
            
            # Only try to land if we're connected
            if hasattr(tello, '_connected') and tello._connected:
                print("[run.py] Landing Tello...")
                tello.land()
            else:
                print("[run.py] Tello not connected, skipping land")
        except Exception as e:
            print(f"[run.py] Error during tello shutdown: {e}")
            # Don't raise - this is expected when drone is disconnected
        print("Bye.")

# Camera
def setup_camera():
    global tello, camera, camera_type
    print(f"[DEBUG] → setup_camera done. camera = {camera}")
    print(f"[DEBUG] camera_type = {camera_type}, camera class = {type(camera).__name__ if camera else 'None'}")
    print("\n[DEBUG] Initializing camera...")
    if camera_type == "TelloCam":
        if tello is None:
            print("❌ Cannot initialize TelloCam: tello is None")
        elif hasattr(tello, '_connected') and not tello._connected:
            print("❌ Cannot initialize TelloCam: dummy tello is not connected")
            # Fallback to WebCam
            camera_type = "WebCam"
            from object_detector.input.WebCam import WebCam
            camera = WebCam()
            print("✅ WebCam initialized as fallback")
        else:
            from object_detector.input.TelloCam import TelloCam
            camera = TelloCam(tello)
            print("✅ TelloCam initialized with shared Tello")
        return

    if camera_type == "SimCam":
        from object_detector.input.SimCam import SimCam
        camera = SimCam()
        return

    if camera_type == "WebCam":
        from object_detector.input.WebCam import WebCam
        camera = WebCam()
        return

    raise ImportError(f"Camera {camera_type} is not implemented.")

# Controller
def setup_controller():
    global controller

    if camera_type == "TelloCam":
        from core.controllers.TelloControllerSmooth import TelloControllerSmooth
        controller = TelloControllerSmooth(tello, False)
        return

    if camera_type == "SimCam":
        from core.controllers.SimController import SimController
        controller = SimController()
        return

    if camera_type == "WebCam":
        from core.controllers.DummyController import DummyController
        controller = DummyController()
        return

# Interface
def setup_interface():
    global app, interface
    
    if interface_type == "QT6Interface":
        from PyQt6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from interfaces.QT6Interface import QT6Interface
        interface = QT6Interface(controller)
        return
    
    if interface_type == "CV2Interface":
        from interfaces.CV2Interface import CV2Interface
        interface = CV2Interface()
        return
    
    raise ImportError(f"Interface {interface_type} is not implemented.")

# Model – Prioritize LightCNNTracker, fallback to the model specified if an error occurs.
def setup_model():
    global model
    try:
        from object_detector.models.LightCNNTracker import LightCNNTracker
        model = LightCNNTracker()
        print("LightCNNTracker loaded successfully.")
    except Exception as e:
        print("Error loading LightCNNTracker:", e)
        # Fallback based on the specified model_type (YoloV8Tracker removed):
        if model_type == "DaSiamMultipleTracker":
            from object_detector.models.DaSiamMultipleTracker import DaSiamMultipleTracker
            model = DaSiamMultipleTracker(interface)
        elif model_type == "DaSiamRPNTracker":
            from object_detector.models.DaSiamRPNTracker import DaSiamRPNTracker
            model = DaSiamRPNTracker(interface)
        elif model_type == "CSRTTracker":
            from object_detector.models.CSRTTracker import CSRTTracker
            model = CSRTTracker(interface)
        else:
            # Default fallback (no YOLO, no YoloV8Tracker)
            from object_detector.models.DaSiamMultipleTracker import DaSiamMultipleTracker
            model = DaSiamMultipleTracker(interface)
        print("Fallback model loaded successfully (YoloV8Tracker is not used).")

# Navigator
def setup_navigator():
    global navigator

    from navigation_plan.navigators.GridNavigator import GridNavigator
    navigator = GridNavigator(model)
    
# Guide
def setup_guide():
    global guide

    from flight_guide.guide.GridGuide import GridGuide
    guide = GridGuide(navigator, controller)
    

#  
# App Setup and Loop
# 

# Setup
def setup():
    interface.set_camera(camera)

    interface.add_on_boundary(model.set_object)
    interface.add_frame_listener(model.on_frame)
    interface.add_frame_listener(navigator.navigate)
    interface.add_frame_listener(guide.update_grid)

# Loop
def loop():
    global camera_type, camera, controller
    
    if interface_type == "QT6Interface":
        from PyQt6.QtCore import QTimer
        from config.settings import MAIN_LOOP_RATE

        def _loop():
            guide.loop()
            controller.loop()
        
        guide_timer = QTimer()
        guide_timer.timeout.connect(_loop)
        guide_timer.start(MAIN_LOOP_RATE)

        app.exec()
        tello_shutdown()

        return
    
    if interface_type == "CV2Interface":
        try:
            while not interface.is_closed:
                # Check for drone disconnection during operation
                if camera_type == "TelloCam" and camera is not None:
                    if hasattr(camera, 'is_connected') and not camera.is_connected():
                        print("[run.py] Drone disconnected during operation! Switching to WebCam...")
                        # Switch to WebCam gracefully
                        try:
                            from object_detector.input.WebCam import WebCam
                            old_camera = camera
                            camera = WebCam()
                            interface.set_camera(camera)
                            camera_type = "WebCam"
                            print("[run.py] Successfully switched to WebCam")
                            
                            # Update controller to dummy
                            from core.controllers.DummyController import DummyController
                            controller = DummyController()
                            
                        except Exception as e:
                            print(f"[run.py] Error switching to WebCam: {e}")
                            break
                
                interface.loop()
                guide.loop()
                controller.loop()
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("Kill Call")
        except Exception as e:
            print("Exception !", e)
            if debug: 
                raise e
        finally:
            tello_shutdown()
        return

def start_face_detection_shared_tello(shared_tello=None):
    global tello, camera_type
    tello = shared_tello

    # Check if we have a real connected drone
    if tello is not None:
        # Check if it's a dummy Tello (has _connected attribute)
        if hasattr(tello, '_connected'):
            if tello._connected:
                print("[INFO] Using shared dummy tello instance (CONNECTED).")
                camera_type = "TelloCam"
                setup_tello()
            else:
                print("[INFO] Dummy tello not connected. Switching to WebCam.")
                camera_type = "WebCam"
        else:
            # It's a real Tello instance - test if it's actually connected
            try:
                # Try to get battery to test if it's actually connected
                battery = tello.get_battery()
                if battery > 0:  # If we can get battery, it's probably connected
                    print("[INFO] Using shared real tello instance (DRONE CONNECTED).")
                    camera_type = "TelloCam"
                    setup_tello()
                else:
                    print("[INFO] Real tello instance exists but not connected. Switching to WebCam.")
                    camera_type = "WebCam"
            except Exception as e:
                print(f"[INFO] Real tello instance exists but connection failed: {e}. Switching to WebCam.")
                camera_type = "WebCam"
    else:
        print("[INFO] No shared tello instance. Switching to WebCam.")
        camera_type = "WebCam"

    print("[DEBUG] → Calling setup_camera()")
    setup_camera()

    print("[DEBUG] → Calling setup_controller()")
    setup_controller()

    print("[DEBUG] → Calling setup_interface()")
    setup_interface()

    print("[DEBUG] → Calling setup_model()")
    setup_model()

    print("[DEBUG] → Calling setup_navigator()")
    setup_navigator()

    print("[DEBUG] → Calling setup_guide()")
    setup_guide()

    print("[DEBUG] → Calling setup()")
    setup()

    print("[DEBUG] → Calling loop()")
    loop()



if __name__ == "__main__":
    start_face_detection_shared_tello()


# if __name__ == "__main__":
#     setup_tello()
#     setup_camera()
#     setup_controller()
#     setup_interface()
#     setup_model()
#     setup_navigator()
#     setup_guide()
#     setup()
#     # Only call execute_attack if tello is connected
#     # if tello is not None:
#     #     execute_attack()

#     loop()
