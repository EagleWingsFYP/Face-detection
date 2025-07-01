import sys, os, time

from dotenv import load_dotenv

# Add the tello module to sys.path if not already present
tello_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tello'))
if tello_path not in sys.path:
    sys.path.insert(0, tello_path)

interface_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../interface'))
if interface_path not in sys.path:
    sys.path.insert(0, interface_path)

from config.settings import debug
#  
# Environment
# 

load_dotenv()

# Set defaults – note that LightCNNTracker is now prioritized.
DEFAULT_CAMERA    = "WebCam"
DEFAULT_INTERFACE = "QT6Interface"
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
    global tello

    if camera_type == "TelloCam":
        from djitellopy import Tello

        tello = Tello()
        tello.connect()
        if bool(int(os.getenv("AUTO_STREAMON", True))): 
            tello.streamon()
        if bool(int(os.getenv("AUTO_TAKEOFF", False))): 
            tello.takeoff()
        
        return

    print("[INFO] Tello not required!")

def tello_shutdown():
    global tello

    if tello and int(os.getenv("AUTO_STREAMON", True)):
        print("Shutdown Sequence _/!\\_")
        tello.streamoff()
        tello.land()
        print("Bye.")

# Camera
def setup_camera():
    global tello, camera
    print("\n[DEBUG] Initializing camera...")
    if camera_type == "TelloCam":
        from object_detector.input.TelloCam import TelloCam
        camera = TelloCam(tello)
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
        model = LightCNNTracker(interface)
        print("LightCNNTracker loaded successfully.")
    except Exception as e:
        print("Error loading LightCNNTracker:", e)
        # Fallback based on the specified model_type (YOLO removed):
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
            # Default fallback
            from object_detector.models.DaSiamMultipleTracker import DaSiamMultipleTracker
            model = DaSiamMultipleTracker(interface)
        print("Fallback model loaded successfully.")

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

#  
# Main
# 

if __name__ == "__main__":
    setup_tello()
    setup_camera()
    setup_controller()
    setup_interface()
    setup_model()
    setup_navigator()
    setup_guide() 
    setup()
    loop()
