from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from djitellopy import Tello
import cv2
import asyncio
from pyzbar.pyzbar import decode
import threading
import uvicorn

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class TelloController:
    def __init__(self):
        self.tello = Tello()
        self.tello.connect()
        self.tello.streamon()

        self.log_file = "movement_log.txt"
        self.qr_data = None
        self.streaming = True
        self.frame_lock = threading.Lock()
        self.video_thread = threading.Thread(target=self.process_video_feed)
        self.video_thread.start()

    async def handle_command(self, command: str) -> str:
        try:
            if command == "forward":
                self.tello.move_forward(30)
            elif command == "backward":
                self.tello.move_back(30)
            elif command == "left":
                self.tello.move_left(30)
            elif command == "right":
                self.tello.move_right(30)
            elif command == "up":
                self.tello.move_up(30)
            elif command == "down":
                self.tello.move_down(30)
            elif command == "rotate_ccw":
                self.tello.rotate_counter_clockwise(30)
            elif command == "rotate_cw":
                self.tello.rotate_clockwise(30)
            elif command == "takeoff":
                self.tello.takeoff()
            elif command == "land":
                self.tello.land()
            else:
                return f"Unknown command: {command}"
            
            self.log_movement(command)
            return f"Successfully executed: {command}"
        except Exception as e:
            return f"Error executing {command}: {str(e)}"

    def log_movement(self, command: str):
        with open(self.log_file, "a") as file:
            file.write(f"{command}\n")

    def process_video_feed(self):
        while self.streaming:
            frame = self.tello.get_frame_read().frame
            if frame is not None:
                # Decode QR codes
                decoded_objects = decode(frame)
                with self.frame_lock:
                    if decoded_objects:
                        self.qr_data = decoded_objects[0].data.decode("utf-8")
                    else:
                        self.qr_data = None
                # Display the video feed with OpenCV (optional for debugging)
                # cv2.imshow("Tello Video Feed", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        cv2.destroyAllWindows()

    def cleanup(self):
        self.streaming = False
        self.video_thread.join()
        self.tello.streamoff()
        self.tello.end()

# Initialize controller
tello_controller = TelloController()

@app.get("/")
async def get_index():
    return {"message": "Tello Control Server Running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send QR data if available
            with tello_controller.frame_lock:
                qr_data = tello_controller.qr_data
            if qr_data:
                await websocket.send_text(f"QR Code Detected: {qr_data}")
            else:
                await websocket.send_text("No QR Code Detected")

            # Wait briefly to reduce server load
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

@app.on_event("shutdown")
def shutdown_event():
    tello_controller.cleanup()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)