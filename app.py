
import cv2
import threading
import time
import json
from flask import Flask, render_template, Response

# --- Game State Variables ---
game_state = {
    "status": "GREEN",  # GREEN, RED, GAME_OVER
    "timer": 0,
}
state_lock = threading.Lock()

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Background Thread for Game Logic ---
def game_logic_thread():
    """
    Manages the game state (GREEN/RED) and timers in a background thread.
    """
    global game_state
    green_duration = 5  # seconds
    red_duration = 4    # seconds

    while True:
        # --- GREEN STATE ---
        with state_lock:
            game_state["status"] = "GREEN"
            game_state["timer"] = green_duration
        
        for i in range(green_duration):
            time.sleep(1)
            with state_lock:
                game_state["timer"] -= 1

        # --- RED STATE ---
        with state_lock:
            # If already GAME_OVER, wait before restarting
            if game_state["status"] == "GAME_OVER":
                game_state["timer"] = 5
                time.sleep(5)
                continue

            game_state["status"] = "RED"
            game_state["timer"] = red_duration

        for i in range(red_duration):
            time.sleep(1)
            with state_lock:
                if game_state["status"] == "GAME_OVER":
                    break # Exit timer loop if game is over
                game_state["timer"] -= 1


# --- Video Streaming and Motion Detection ---
def generate_frames():
    """
    Captures frames from the camera, performs motion detection,
    and yields frames as a multipart HTTP response.
    """
    global game_state
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not start camera.")

    previous_frame = None
    motion_threshold = 5000 # Adjust this value based on sensitivity

    while True:
        success, frame = camera.read()
        if not success:
            break

        # Motion Detection Logic
        with state_lock:
            current_status = game_state["status"]

        if current_status == "RED":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if previous_frame is None:
                previous_frame = gray
                continue

            frame_delta = cv2.absdiff(previous_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > motion_threshold:
                    motion_detected = True
                    break
            
            if motion_detected:
                with state_lock:
                    game_state["status"] = "GAME_OVER"
            
            previous_frame = gray
        else:
            # Reset previous_frame when not in RED state
            previous_frame = None

        # Draw status on the frame
        with state_lock:
            display_status = game_state["status"]
            display_timer = game_state["timer"]
        
        color = {"GREEN": (0, 255, 0), "RED": (0, 0, 255), "GAME_OVER": (0, 255, 255)}[display_status]
        cv2.putText(frame, f"STATUS: {display_status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"TIMER: {display_timer}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)


        # Encode the frame in JPEG format
        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        # Yield the output frame in the byte format
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
    """API to get current game state."""
    with state_lock:
        return json.dumps(game_state)

# --- Main Execution ---
if __name__ == '__main__':
    # Start the game logic thread
    logic_thread = threading.Thread(target=game_logic_thread)
    logic_thread.daemon = True
    logic_thread.start()
    
    # Run the Flask app
    # Use threaded=True to handle multiple concurrent requests
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
