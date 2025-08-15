import cv2
import numpy as np
import pyautogui
from collections import deque
import time
import keyboard
import winsound
import pygame
import threading

pygame.mixer.init()

# ===== Helper Functions =====
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

# ===== Settings =====
MIN_ZONE_WIDTH = 8
MIN_ZONE_HEIGHT = 8
MIN_CURSOR_WIDTH = 5
MIN_CURSOR_HEIGHT = 5
ZONE_DELAY_FRAMES = 3
FRAME_DELAY = 1.0 / 100
CURSOR_RADIUS = 8

# ===== Initialization =====
white_zone_history = deque(maxlen=ZONE_DELAY_FRAMES)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

print("Нажмите ESC для выхода.")
last_press_time = 0
press_delay = 0.6
prev_frame_time = time.time()
script_enabled = False

def beep_toggle(on: bool):
    sound_file = "sounds/on.wav" if on else "sounds/off.wav"
    sound = pygame.mixer.Sound(sound_file)
    sound.set_volume(0.1)
    sound.play()

# ===== Threading for Frame Capture =====
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

# ===== Main Loop =====
while True:
    with frame_lock:
        if shared_frame is None:
            continue
        frame = shared_frame.copy()

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ===== Key Press Handling =====
    if keyboard.is_pressed('p'):
        script_enabled = not script_enabled
        beep_toggle(script_enabled)
        time.sleep(0.3)

    # ===== Cursor (Red) Detection =====
    lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 120, 120])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.bitwise_or(
        cv2.inRange(hsv, lower_red1, upper_red1),
        cv2.inRange(hsv, lower_red2, upper_red2)
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

    # ===== Zone (White) Detection =====
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
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)

    white_zone_history.append(white_rects)

    # ===== Intersection and Action =====
    if script_enabled:
        intersect_white = False
        delayed_white_rects = white_zone_history[0] if len(white_zone_history) >= ZONE_DELAY_FRAMES else []
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

    # ===== Display Status =====
    status_text = "+" if script_enabled else "-"
    status_color = (0, 255, 0) if script_enabled else (0, 0, 255)
    cv2.putText(frame, status_text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
    
    cv2.imshow("Detection", frame)

    # ===== Frame Rate Control =====
    elapsed = time.time() - prev_frame_time
    if elapsed < FRAME_DELAY:
        time.sleep(FRAME_DELAY - elapsed)
    prev_frame_time = time.time()

    # ===== Exit Condition =====
    if cv2.waitKey(1) == 27 or keyboard.is_pressed('esc'):
        stop_threads = True
        break

# ===== Cleanup =====
cap.release()
cv2.destroyAllWindows()