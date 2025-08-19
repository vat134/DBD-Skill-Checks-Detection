import cv2
import numpy as np
import pyautogui
from collections import deque
import time
from datetime import datetime
import keyboard
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1" # Hide pygame init message
import pygame
import threading
from pathlib import Path

# Initialize the pygame mixer for sound effects
pygame.mixer.init()

# ===================================================================== #
#                          HELPER FUNCTIONS                             #
# ===================================================================== #

def get_center(x, y, w, h):
    return (x + w // 2, y + h // 2)

def circle_rect_intersect(circle_center, radius, rect):
    cx, cy = circle_center
    rx, ry, rw, rh = rect

    # Find the closest point on the rectangle to the circle's center
    nearest_x = max(rx, min(cx, rx + rw))
    nearest_y = max(ry, min(cy, ry + rh))

    # Calculate the distance from the circle's center to this point
    dx = cx - nearest_x
    dy = cy - nearest_y

    # Return true if the distance is less than or equal to the radius
    return (dx * dx + dy * dy) <= (radius * radius)

# ===================================================================== #
#                             CONFIGURATION                             #
# ===================================================================== #

# --- Detection Parameters ---
MIN_ZONE_WIDTH = 8
MIN_ZONE_HEIGHT = 8
MIN_CURSOR_WIDTH = 5
MIN_CURSOR_HEIGHT = 5
CURSOR_RADIUS = 5

# --- Performance & Logic ---
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
FRAME_DELAY = 1.0 / 120        # Target ~120 FPS
ZONE_DELAY_FRAMES = 3          # How many frames to delay the zone detection for action
WHITE_ZONE_PERSISTENCE = 10    # Number of frames to check for a stable zone
STABLE_MIN_COUNT = 7           # Min frames a zone must appear in to be "stable"
ACTION_COOLDOWN = 0.6          # Cooldown in seconds between key presses

# --- Sound File Paths ---
base_dir = Path(__file__).parent
SOUND_ON_PATH = str(base_dir / "sounds" / "on.wav")
SOUND_OFF_PATH = str(base_dir / "sounds" / "off.wav")

# ===================================================================== #
#                       INITIALIZATION & GLOBALS                        #
# ===================================================================== #

# --- State Variables ---
script_enabled = False
stop_threads = False
last_press_time = 0
prev_frame_time = time.time()
shared_frame = None

# --- Data Structures ---
white_zone_history = deque(maxlen=WHITE_ZONE_PERSISTENCE)
frame_lock = threading.Lock()

# --- Camera Setup ---
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

print("Script started. Press 'P' to toggle, 'Alt+P' to exit.")
print("Don't forget OBS!!!!")

# ===================================================================== #
#                          SOUND FUNCTION                               #
# ===================================================================== #

def beep_toggle(on: bool):
    """Plays a sound to indicate if the script is enabled or disabled."""
    sound_file = SOUND_ON_PATH if on else SOUND_OFF_PATH
    sound = pygame.mixer.Sound(sound_file)
    sound.set_volume(0.1)  # volume from 0.0 to 1.0
    sound.play()

# ===================================================================== #
#                      CAMERA CAPTURE THREAD                            #
# ===================================================================== #

def capture_thread():
    """
    Reads frames from the camera in a separate thread to prevent I/O blocking
    in the main processing loop, ensuring a smoother frame rate.
    """
    global shared_frame, stop_threads
    while not stop_threads:
        ret, frame = cap.read()
        if not ret:
            continue
        with frame_lock:
            shared_frame = frame.copy()

# Start the capture thread as a daemon
threading.Thread(target=capture_thread, daemon=True).start()

# ===================================================================== #
#                              MAIN LOOP                                #
# ===================================================================== #

while True:
    # ------------------------- Frame Acquisition ------------------------- #
    with frame_lock:
        if shared_frame is None:
            continue
        frame = shared_frame.copy()

    # Convert the frame to the HSV color space for better color detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ----------------------- Keyboard Input Handling ----------------------- #
    if keyboard.is_pressed('p'):
        script_enabled = not script_enabled
        beep_toggle(script_enabled)

        # Active status for console
        current_time_for_console = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "on" if script_enabled else "off"
        print(f"Script is {status} в {current_time_for_console}")

        time.sleep(0.3) # Debounce to prevent rapid toggling

    # ------------------------- Cursor Detection (Red) ------------------------ #
    lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 120, 120])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.bitwise_or(
        cv2.inRange(hsv, lower_red1, upper_red1),
        cv2.inRange(hsv, lower_red2, upper_red2)
    )
    # Use morphological operations to remove noise from the mask
    kernel = np.ones((3,3), np.uint8)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel, iterations=1)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_DILATE, kernel, iterations=1)

    contours_cursor, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cursor_centers = []
    for cnt in contours_cursor:
        x, y, w, h = cv2.boundingRect(cnt)
        if w >= MIN_CURSOR_WIDTH and h >= MIN_CURSOR_HEIGHT:
            center = get_center(x, y, w, h)
            cursor_centers.append(center)
            cv2.circle(frame, center, CURSOR_RADIUS, (0, 0, 255), 2) # Draw red circle

    # ------------------------- Zone Detection (White) ------------------------ #
    lower_white = np.array([0, 0, 155])
    upper_white = np.array([180, 15, 175])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_OPEN, kernel, iterations=1)
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_DILATE, kernel, iterations=1)

    white_rects = []
    contours_white, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_white:
        x, y, w, h = cv2.boundingRect(cnt)
        if w >= MIN_ZONE_WIDTH and h >= MIN_ZONE_HEIGHT:
            white_rects.append((x, y, w, h))
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2) # Draw white rect

    white_zone_history.append(white_rects)

    # -------------------- Stable White Zone Filtering -------------------- #
    # This section identifies zones that appear consistently over several frames
    # to prevent actions based on flickering or noisy detections.

    def zone_similar(z1, z2, tol=15):
        """
        Checks if two zones (rects) are in a similar position and size 
        z1, z2: (x, y, w, h), tol — tolerance on coordinates and size 
        """
        return (
            abs(z1[0] - z2[0]) <= tol and
            abs(z1[1] - z2[1]) <= tol and
            abs(z1[2] - z2[2]) <= tol and
            abs(z1[3] - z2[3]) <= tol
        )

    stable_white_rects_list = []
    if len(white_zone_history) == WHITE_ZONE_PERSISTENCE:
        # Check zones from the oldest relevant frame in history
        for i in range(len(white_zone_history)):
            frame_zones = white_zone_history[i]
            stable_zones = []
            for zone in frame_zones:
                count = 1
                # Count how many times a similar zone appears in the entire history
                for j, prev in enumerate(list(white_zone_history)):
                    if j == i:
                        continue
                    if any(zone_similar(zone, z) for z in prev):
                        count += 1
                # If the zone is persistent enough, consider it stable
                if count >= STABLE_MIN_COUNT:
                    stable_zones.append(zone)
            stable_white_rects_list.append(stable_zones)
    else:
        stable_white_rects_list = [white_rects] * len(white_zone_history)

    # For intersection, we take stable zones from the 3rd previous frame.
    if len(stable_white_rects_list) >= 3:
        stable_white_rects = stable_white_rects_list[0]
    else:
        stable_white_rects = stable_white_rects_list[-1] if stable_white_rects_list else []

    # Visualize the currently detected stable zones for debugging
    for x, y, w, h in stable_white_rects_list[-1] if stable_white_rects_list else []:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2) # Draw green rect


    # ---------------------- Intersection & Action Logic ---------------------- #
    if script_enabled:
        intersect_white = False
        delayed_white_rects = stable_white_rects
        if cursor_centers:
            centers_np = np.array(cursor_centers)
            for rect in delayed_white_rects:
                rx, ry, rw, rh = rect
                cx, cy = centers_np[:,0], centers_np[:,1]
                nearest_x = np.clip(cx, rx, rx+rw)
                nearest_y = np.clip(cy, ry, ry+rh)
                dx = cx - nearest_x
                dy = cy - nearest_y
                # Check if any detected cursor intersects with a stable zone
                if np.any((dx*dx + dy*dy) <= (CURSOR_RADIUS*CURSOR_RADIUS)):
                    intersect_white = True
                    break

        current_time = time.time()
        if intersect_white and (current_time - last_press_time >= ACTION_COOLDOWN):
            pyautogui.press('space')
            last_press_time = current_time
            cv2.putText(frame, "PRESS SPACE (WHITE)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    # ------------------------ Status Display & Output ------------------------ #
    status_text = "+" if script_enabled else "-"
    status_color = (0, 255, 0) if script_enabled else (0, 0, 255)
    cv2.putText(frame, status_text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)

    # Uncomment the line below to show the camera feed window
    #cv2.imshow("Detection", frame)
    cv2.waitKey(1)
    
    # -------------------------- Frame Rate Control ------------------------- #
    elapsed = time.time() - prev_frame_time
    if elapsed < FRAME_DELAY:
        time.sleep(FRAME_DELAY - elapsed)
    prev_frame_time = time.time()

    # ----------------------------- Exit Condition ---------------------------- #
    if keyboard.is_pressed('alt+p'):
        stop_threads = True
        break

# ===================================================================== #
#                                CLEANUP                                #
# ===================================================================== #

print("Bye, (◕_◕)ﾉ  See you next time!")
cap.release()
cv2.destroyAllWindows()
