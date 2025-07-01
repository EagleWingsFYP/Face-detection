
# 
# Imports
# 

import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
import cv2
from config.settings import platform


# 
# get_video_inputs function
# 

def get_video_inputs():
    video_inputs = {}
    index = 0

    if platform == 'Linux':
        import pyudev

        # Use pyudev to get video devices on Linux
        context = pyudev.Context()
        for device in context.list_devices(subsystem='video4linux'):
            if 'ID_VIDEO' in device:
                name = device.get('ID_MODEL', 'Unknown Camera')
                device_type = 'WebCam' if 'usb' in device.device_type else 'Integrated Camera'
                video_inputs[index] = {'name': name, 'type': device_type}
                index += 1

    elif platform == 'Windows':
        import wmi
        c = wmi.WMI()
        for device in c.Win32_PnPEntity():
            if "camera" in device.Caption.lower() or "video" in device.Caption.lower():
                device_type = 'WebCam' if 'usb' in device.Caption.lower() else 'Integrated Camera'
                video_inputs[index] = {'name': device.Caption, 'type': device_type}
                index += 1

    else:
        pass
        # raise NotImplementedError(f"Unsupported platform: {platform}")


    while index < 10:
        cap = cv2.VideoCapture(index)
        
        if not cap.isOpened():
            break

        # Frame test
        ret, frame = cap.read()
        device = video_inputs.get(index, {'type':  f"Unknown", 'name': f"Camera {index}"})

        if ret:
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)


            video_inputs[index] = {'name':  device['name'], 'width': width, 'height': height, 'readable': True, 'type': device['type']}
        else:
            video_inputs[index] = {'name':  device['name'], 'readable': False, 'type': device['type']}

        cap.release()
        index += 1

    return video_inputs
