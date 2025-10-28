import cv2
import threading
import time
import json
import os
import numpy as np
from flask import Flask, render_template, Response, request
from flask_cors import CORS

# --- Configuration ---
MOTION_THRESHOLD = 1000  # Sensitivity for motion detection. Higher value means less sensitive.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))  # Camera device index (e.g. 0:/dev/video0, 2:/dev/video2)

# --- Game State Variables ---
game_state = {
    "mode": "IDLE",  # IDLE, GREEN, RED, GAME_OVER
    "penalty_flash": False,
    "last_penalty_time": 0,
}
state_lock = threading.Lock()

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Video Streaming and Motion Detection ---
def generate_frames():
    """
    Captures frames from the camera, performs motion detection if mode is RED,
    and yields frames as a multipart HTTP response.
    """
    global game_state
    print(f"Initializing camera with index {CAMERA_INDEX}...")
    camera = cv2.VideoCapture(CAMERA_INDEX)
    try:
        camera_opened = camera.isOpened()
        if not camera_opened:
            print(f"Warning: Could not start camera index {CAMERA_INDEX}. Displaying a black screen instead.")

        previous_frame = None

        while True:
            if not camera_opened:
                # Fallback black screen
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "Camera not available", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
                if flag:
                    yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                          bytearray(encodedImage) + b'\r\n')
                time.sleep(0.1)
                continue

            success, frame = camera.read()
            if not success:
                break

            with state_lock:
                current_mode = game_state["mode"]

            if current_mode == "RED":
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if previous_frame is None:
                    previous_frame = gray
                    time.sleep(0.05)
                    continue

                frame_delta = cv2.absdiff(previous_frame, gray)
                thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                motion_detected = any(cv2.contourArea(c) > MOTION_THRESHOLD for c in contours)

                if motion_detected:
                    with state_lock:
                        current_time = time.time()
                        if current_time - game_state.get("last_penalty_time", 0) > 1.0:
                            if not game_state["penalty_flash"]:
                                game_state["penalty_flash"] = True
                                game_state["last_penalty_time"] = current_time
                
                previous_frame = gray
            else:
                previous_frame = None

            with state_lock:
                display_mode = game_state["mode"]
                last_penalty = game_state.get("last_penalty_time", 0)

            color = {"GREEN": (0, 255, 0), "RED": (0, 0, 255), "GAME_OVER": (0, 255, 255), "IDLE": (255, 255, 255)}.get(display_mode, (255, 255, 255))
            cv2.putText(frame, f"MODE: {display_mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            
            if time.time() - last_penalty < 1.0:
                cv2.putText(frame, "MOTION DETECTED!", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            if not flag:
                continue

            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                  bytearray(encodedImage) + b'\r\n')
    finally:
        camera.release()
        print("Camera released.")

# --- Flask Routes ---
@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/gamestate')
def get_gamestate():
    """API to get current game state."""
    with state_lock:
        state_to_send = game_state.copy()
        if game_state["penalty_flash"]:
            game_state["penalty_flash"] = False
    return json.dumps(state_to_send)

@app.route('/api/start', methods=['POST'])
def start_game():
    """API to start the game (sets mode to GREEN)."""
    with state_lock:
        game_state["mode"] = "GREEN"
        game_state["penalty_flash"] = False
        game_state["last_penalty_time"] = 0
    return json.dumps(game_state)

@app.route('/api/end', methods=['POST'])
def end_game():
    """API to end the game (sets mode to GAME_OVER)."""
    with state_lock:
        game_state["mode"] = "GAME_OVER"
    return json.dumps(game_state)

@app.route('/api/setmode', methods=['POST'])
def set_mode():
    """API for the client to set the game mode (e.g., GREEN, RED)."""
    data = request.get_json(silent=True)
    if not data:
        return json.dumps({"status": "error", "message": "Invalid JSON"}), 400
        
    new_mode = data.get("mode")
    if new_mode in ["GREEN", "RED"]:
        with state_lock:
            game_state["mode"] = new_mode
        return json.dumps({"status": "success", "new_mode": new_mode})
    return json.dumps({"status": "error", "message": "Invalid mode"}), 400

# --- Main Execution ---
if __name__ == '__main__':
    # For production, use a proper WSGI server like Gunicorn or uWSGI
    # Example: gunicorn --workers 4 --threads 100 --bind 0.0.0.0:5000 app:app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
