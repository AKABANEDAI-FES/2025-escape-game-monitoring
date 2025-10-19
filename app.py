
import cv2
import threading
import time
import json
import numpy as np
from flask import Flask, render_template, Response

# --- Game State Variables ---
game_state = {
    "mode": "GREEN",
    "total_time": 180,
    "interval_timer": 20,
    "penalty_flash": False,
    "last_penalty_time": 0, # To manage penalty interval
}
state_lock = threading.Lock()


# --- Flask App Initialization ---
app = Flask(__name__)

# --- Background Thread for Game Logic ---
def game_logic_thread():
    """
    Manages the game state (GREEN/RED/GAME_OVER) and timers in a background thread.
    """
    global game_state
    interval_duration = 20  # 20 seconds for both GREEN and RED

    while True:
        time.sleep(1)
        with state_lock:
            # If game is over, do nothing
            if game_state["mode"] == "GAME_OVER":
                continue

            # Decrement timers
            game_state["total_time"] -= 1
            game_state["interval_timer"] -= 1

            # Check for game over
            if game_state["total_time"] <= 0:
                game_state["mode"] = "GAME_OVER"
                game_state["total_time"] = 0
                continue

            # Check for state transition
            if game_state["interval_timer"] <= 0:
                if game_state["mode"] == "GREEN":
                    game_state["mode"] = "RED"
                elif game_state["mode"] == "RED":
                    game_state["mode"] = "GREEN"
                game_state["interval_timer"] = interval_duration


# --- Video Streaming and Motion Detection ---
def generate_frames():
    """
    Captures frames from the camera, performs motion detection,
    and yields frames as a multipart HTTP response.
    Handles camera errors gracefully by providing a fallback stream.
    """
    global game_state, penalty_applied_in_frame
    camera = cv2.VideoCapture(0)
    camera_opened = camera.isOpened()
    if not camera_opened:
        print("Warning: Could not start camera. Displaying a black screen instead.")

    previous_frame = None
    motion_threshold = 1000

    while True:
        if not camera_opened:
            # Create a black frame with an error message if camera is not available
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Camera not available", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            if flag:
                yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                      bytearray(encodedImage) + b'\r\n')
            time.sleep(0.1) # Limit frame rate
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
                time.sleep(0.1)
                continue

            frame_delta = cv2.absdiff(previous_frame, gray)
            thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = any(cv2.contourArea(c) > motion_threshold for c in contours)

            if motion_detected:
                with state_lock:
                    current_time = time.time()
                    if current_time - game_state["last_penalty_time"] > 1.0:
                        if game_state["total_time"] > 0:
                            game_state["total_time"] = max(0, game_state["total_time"] - 5)
                            game_state["penalty_flash"] = True
                            game_state["last_penalty_time"] = current_time
            
            previous_frame = gray
        else:
            previous_frame = None

        # Draw status on the frame
        with state_lock:
            display_mode = game_state["mode"]
            display_total_time = game_state["total_time"]
            display_interval_timer = game_state["interval_timer"]

        color = {"GREEN": (0, 255, 0), "RED": (0, 0, 255), "GAME_OVER": (0, 255, 255)}.get(display_mode, (255, 255, 255))
        cv2.putText(frame, f"MODE: {display_mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"TOTAL TIME: {display_total_time}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"INTERVAL: {display_interval_timer}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
              bytearray(encodedImage) + b'\r\n')

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
    """API to get current game state and then reset the flash flag."""
    with state_lock:
        # Copy the state to send before modifying it
        state_to_send = game_state.copy()
        # Reset the flash so it only fires once per event
        if game_state["penalty_flash"]:
            game_state["penalty_flash"] = False
        return json.dumps(state_to_send)

@app.route('/api/restart', methods=['POST'])
def restart_game():
    """API to reset the game state."""
    global game_state
    with state_lock:
        game_state = {
            "mode": "GREEN",
            "total_time": 180,
            "interval_timer": 20,
            "penalty_flash": False,
            "last_penalty_time": 0,
        }
    return json.dumps(game_state)

# --- Main Execution ---
if __name__ == '__main__':
    # Start the game logic thread
    logic_thread = threading.Thread(target=game_logic_thread)
    logic_thread.daemon = True
    logic_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
