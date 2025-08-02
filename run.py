import sys, os, time

from dotenv import load_dotenv

tello_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tello'))
if tello_path not in sys.path:
    sys.path.insert(0, tello_path)

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

interface_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../interface'))
if interface_path not in sys.path:
    sys.path.insert(0, interface_path)

from modules.models.attack import execute_attack
from config.settings import debug

load_dotenv()

DEFAULT_CAMERA    = "WebCam"
DEFAULT_INTERFACE = "CV2Interface"
DEFAULT_MODEL     = "DaSiamRPNTracker"  

camera_type    = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CAMERA",    DEFAULT_CAMERA   )
interface_type = sys.argv[2] if len(sys.argv) > 2 else os.getenv("INTERFACE", DEFAULT_INTERFACE)
model_type     = sys.argv[3] if len(sys.argv) > 3 else os.getenv("MODEL",     DEFAULT_MODEL    )


tello = None
app = None
camera = None
controller = None
interface = None
model = None
navigator = None
guide = None


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
            if hasattr(tello, '_connected') and tello._connected:
                print("[run.py] Stopping Tello stream during shutdown...")
                tello.streamoff()
            else:
                print("[run.py] Tello not connected, skipping streamoff")
            
            if hasattr(tello, '_connected') and tello._connected:
                print("[run.py] Landing Tello...")
                tello.land()
            else:
                print("[run.py] Tello not connected, skipping land")
        except Exception as e:
            print(f"[run.py] Error during tello shutdown: {e}")
        print("Bye.")

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

def setup_model():
    global model
    try:
        from object_detector.models.LightCNNTracker import LightCNNTracker
        model = LightCNNTracker()
        print("LightCNNTracker loaded successfully.")
    except Exception as e:
        print("Error loading LightCNNTracker:", e)
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
            from object_detector.models.DaSiamMultipleTracker import DaSiamMultipleTracker
            model = DaSiamMultipleTracker(interface)
        print("Fallback model loaded successfully (YoloV8Tracker is not used).")

def setup_navigator():
    global navigator

    from navigation_plan.navigators.GridNavigator import GridNavigator
    navigator = GridNavigator(model)
    
def setup_guide():
    global guide

    from flight_guide.guide.GridGuide import GridGuide
    guide = GridGuide(navigator, controller)
    


def setup():
    interface.set_camera(camera)

    interface.add_on_boundary(model.set_object)
    interface.add_frame_listener(model.on_frame)
    interface.add_frame_listener(navigator.navigate)
    interface.add_frame_listener(guide.update_grid)

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
                if camera_type == "TelloCam" and camera is not None:
                    if hasattr(camera, 'last_check_time'):
                        if time.time() - camera.last_check_time < 5.0:
                            pass  # Skip check if less than 5 seconds since last check
                        else:
                            camera.last_check_time = time.time()
                            if hasattr(camera, 'is_connected') and not camera.is_connected:
                                print("[run.py] Drone disconnected during operation! Switching to WebCam...")
                                try:
                                    from object_detector.input.WebCam import WebCam
                                    old_camera = camera
                                    camera = WebCam()
                                    interface.set_camera(camera)
                                    camera_type = "WebCam"
                                    print("[run.py] Successfully switched to WebCam")
                                    
                                    from core.controllers.DummyController import DummyController
                                    controller = DummyController()
                                    
                                except Exception as e:
                                    print(f"[run.py] Error switching to WebCam: {e}")
                                    break
                    else:
                        camera.last_check_time = time.time()
                
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

    if tello is not None:
        if hasattr(tello, '_connected'):
            if tello._connected:
                print("[INFO] Using shared dummy tello instance (CONNECTED).")
                camera_type = "TelloCam"
                setup_tello()
            else:
                print("[INFO] Dummy tello not connected. Switching to WebCam.")
                camera_type = "WebCam"
        else:
            try:
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



