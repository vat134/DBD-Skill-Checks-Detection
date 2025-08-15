import cv2
import numpy as np
import pyautogui
from collections import deque
import time
import keyboard
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1" # Hide pygame init message
import pygame
import threading
from pathlib import Path

# =====================
#      Settings (changeable parameters)
# =====================
MIN_ZONE_WIDTH = 8           # Minimum width of the white zone
MIN_ZONE_HEIGHT = 8          # Minimum height of the white zone
MIN_CURSOR_WIDTH = 5         # Minimum width of the cursor
MIN_CURSOR_HEIGHT = 5        # Minimum height of the cursor
FRAME_DELAY = 1.0 / 120      # Delay between frames (FPS)
CURSOR_RADIUS = 8            # Cursor radius
WHITE_ZONE_PERSISTENCE = 10  # How many consecutive frames the zone should exist
STABLE_MIN_COUNT = 7         # Minimum frames for a stable zone
press_delay = 0.6            # Delay between presses

# --- Color ranges (HSV) ---
# Cursor (red)
LOWER_RED1 = np.array([0, 120, 120])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([160, 120, 120])
UPPER_RED2 = np.array([180, 255, 255])
# White zone
LOWER_WHITE = np.array([0, 0, 155])
UPPER_WHITE = np.array([180, 15, 175])

# =====================
#      Initialization
# =====================
pygame.mixer.init()
base_dir = Path(__file__).parent  # Path to the script directory
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Reduce resolution for acceleration
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
print("Press alt + p to exit.")

# =====================
#      Global variables
# =====================
white_zone_history = deque(maxlen=WHITE_ZONE_PERSISTENCE)
last_press_time = 0
prev_frame_time = time.time()
script_enabled = False

# =====================
#      Beep sound
# =====================
def beep_toggle(on: bool):
    sound_file = str(base_dir / "sounds" / ("on.wav" if on else "off.wav"))
    sound = pygame.mixer.Sound(sound_file)
    sound.set_volume(0.1)  # Volume from 0.0 to 1.0
    sound.play()

# =====================
#      Helper functions
# =====================
def get_center(x, y, w, h):
    return (x + w // 2, y + h // 2)

def circle_rect_intersect(circle_center, radius, rect):
    cx, cy = circle_center
    rx, ry, rw, rh = rect
    nearest_x = max(rx, min(cx, rx + rw))
    nearest_y = max(ry, min(cy, ry + rh))
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx * dx + dy * dy) <= (radius * radius)

# =====================
#      Multithreaded frame processing
# =====================
frame_lock = threading.Lock()
shared_frame = None
stop_threads = False

def capture_thread():
    global shared_frame, stop_threads
    while not stop_threads:
        ret, frame = cap.read()
        if not ret:
            continue
        with frame_lock:
            shared_frame = frame.copy()

threading.Thread(target=capture_thread, daemon=True).start()

# =====================
#      Main loop
# =====================
while True:
    # Get frame
    with frame_lock:
        if shared_frame is None:
            continue
        frame = shared_frame.copy()

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # --- "P" key processing (enable/disable script) ---
    if keyboard.is_pressed('p'):
        script_enabled = not script_enabled
        beep_toggle(script_enabled)
        time.sleep(0.3)


    # --- Cursor processing (search for red circle) ---
    mask_red = cv2.bitwise_or(
        cv2.inRange(hsv, LOWER_RED1, UPPER_RED1),
        cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    )
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
            cv2.circle(frame, center, CURSOR_RADIUS, (0, 0, 255), 2)


    # --- Search for white zones ---
    mask_white = cv2.inRange(hsv, LOWER_WHITE, UPPER_WHITE)
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_OPEN, kernel, iterations=1)
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_DILATE, kernel, iterations=1)

    white_rects = []
    contours_white, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_white:
        x, y, w, h = cv2.boundingRect(cnt)
        if w >= MIN_ZONE_WIDTH and h >= MIN_ZONE_HEIGHT:
            white_rects.append((x, y, w, h))
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)

    white_zone_history.append(white_rects)

    # --- Filtering of stable white zones ---
    def zone_similar(z1, z2, tol=15):
        return (
            abs(z1[0] - z2[0]) <= tol and
            abs(z1[1] - z2[1]) <= tol and
            abs(z1[2] - z2[2]) <= tol and
            abs(z1[3] - z2[3]) <= tol
        )

    stable_white_rects_list = []
    if len(white_zone_history) == WHITE_ZONE_PERSISTENCE:
        for i in range(len(white_zone_history)):
            frame_zones = white_zone_history[i]
            stable_zones = []
            for zone in frame_zones:
                count = 1
                for j, prev in enumerate(list(white_zone_history)):
                    if j == i:
                        continue
                    if any(zone_similar(zone, z) for z in prev):
                        count += 1
                if count >= STABLE_MIN_COUNT:
                    stable_zones.append(zone)
            stable_white_rects_list.append(stable_zones)
    else:
        stable_white_rects_list = [white_rects] * len(white_zone_history)

    # For intersection, we take stable zones from the 3rd previous frame
    if len(stable_white_rects_list) >= 3:
        stable_white_rects = stable_white_rects_list[0]
    else:
        stable_white_rects = stable_white_rects_list[-1] if stable_white_rects_list else []

    # Visualization of stable zones of the current frame
    for x, y, w, h in stable_white_rects_list[-1] if stable_white_rects_list else []:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # --- Intersection and pressing (space press logic) ---
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
                if np.any((dx*dx + dy*dy) <= (CURSOR_RADIUS*CURSOR_RADIUS)):
                    intersect_white = True
                    break

        current_time = time.time()

        if intersect_white and (current_time - last_press_time >= press_delay):
            pyautogui.press('space')
            last_press_time = current_time
            cv2.putText(frame, "PRESS SPACE (WHITE)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    # --- Displaying the state (on/off indicator) ---
    status_text = "+" if script_enabled else "-"
    status_color = (0, 255, 0) if script_enabled else (0, 0, 255)
    cv2.putText(frame, status_text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)

    # --- Displaying the window ---
    cv2.imshow("Detection", frame)
    cv2.waitKey(1)

    # --- FPS control ---
    elapsed = time.time() - prev_frame_time
    if elapsed < FRAME_DELAY:
        time.sleep(FRAME_DELAY - elapsed)
    prev_frame_time = time.time()

    # --- Exit on Alt+P key combination ---
    if keyboard.is_pressed('alt+p'):
        stop_threads = True
        break

cap.release()
cv2.destroyAllWindows()
