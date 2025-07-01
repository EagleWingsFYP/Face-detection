import asyncio
import websockets
import threading
import json
import cv2
import numpy as np
from PIL import Image
import io

class SimCam:

    def __init__(self, run_on_start=True, host="127.0.0.1", port=8091):
        self.connection = None
        self.loop = asyncio.new_event_loop()
        self.lock = threading.Lock()
        self.host = host
        self.port = port
        self.latest_frame = None
        self.frame_in_process = False

        if run_on_start:
            self.start_server()
            self.run_background_process()

    def start_server(self):
        thread = threading.Thread(target=self.run_server)
        thread.daemon = True
        thread.start()

    def run_server(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_websocket_server())

    async def run_websocket_server(self):
        async with websockets.serve(self.handle_connection, self.host, self.port):
            print(f"SimCamera listening on ws://{self.host}:{self.port}")
            await asyncio.Future()

    async def connect(self, websocket):
        self.connection = websocket
        print("SimCamera connected.")
        await self.send_message({"status": "connected"})

    async def handle_connection(self, websocket, path):
        await self.connect(websocket)
        try:
            async for message in websocket:
                if message == '1':
                    await self.request_and_process_frame()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await self.end()

    async def request_and_process_frame(self):
        if self.frame_in_process:
            print("Frame request is already in process.")
            return

        try:
            self.frame_in_process = True  # Mark that a frame is being processed

            await self.send_message('1')

            frame_data = await self.receive_frame_data()
            if frame_data:
                image = Image.open(io.BytesIO(frame_data))
                processed_frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                with self.lock:
                    self.latest_frame = processed_frame

            else:
                print("No frame data received.")

        except Exception as e:
            print(f"Error processing frame: {e}")
        finally:
            self.frame_in_process = False

    async def receive_frame_data(self):
        if self.connection:
            try:
                frame_data = await self.connection.recv()
                return frame_data
            except Exception as e:
                print(f"Error receiving frame data: {e}")
                return None

    async def end(self):
        if self.connection:
            await self.connection.close()
            print("SimCamera connection ended.")

    async def send_message(self, message):
        if self.connection:
            await self.connection.send(json.dumps(message))

    def run_background_process(self):
        threading.Thread(target=self.background_process, daemon=True).start()

    def background_process(self):
        asyncio.set_event_loop(self.loop)
        asyncio.create_task(self.send_and_receive_frames())

    async def send_and_receive_frames(self):
        while True:
            await self.send_request_for_frame()  # Replace with your actual logic to send '1'
            frame = await self.wait_for_frame()  # Replace with your actual logic for receiving the frame
            self.latest_frame = self.process_frame(frame)  # Implement your frame processing logic here

    def frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame
            else:
                return np.zeros((480, 640, 3), dtype=np.uint8)

    def exit(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
