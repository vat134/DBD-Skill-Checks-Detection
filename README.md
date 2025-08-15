# DBD Skill Checks Detection — README
\*README for a V6.2\*

## Description
This script is designed for automatic detection and reaction to “white zones” (skill checks) in the game Dead by Daylight using computer vision.
It uses a camera to capture the image, highlights areas of interest, and automatically presses a key if the cursor overlaps a stable white zone.

## Key Features
- Detection of the red cursor and white zones in the camera feed.
- Automatic key press (default — Space) when the cursor overlaps a stable white zone.
- Real-time visualization of detected and stable zones.
- Filtering of false positives through zone history analysis (stability check).
- Multithreaded processing: frame capture and processing are performed in parallel for high performance.
- Morphological operations to improve zone detection accuracy and reduce noise.
- Flexible parameter adjustment (zone sizes, stability frame count, tolerances).

## Advantages & Improvements
- **Multithreading**: ensures high FPS and responsive interface.
- **Stable zones**: a zone is considered valid only if it is detected in the same position in most of the last 10 frames, eliminating random flashes and noise.
- **History delay**: the decision is based on the zone from the 3rd previous frame to avoid false triggers from newly appeared objects.
- **Morphological filters**: reduce noise influence and improve detection quality.
- **Vectorization & optimization**: faster intersection checks using NumPy.
- **Flexible visualization**: stable zones are highlighted in green for clarity.

## How to Run
1. Install dependencies:
   - Python 3.7+
   - opencv-python
   - numpy
   - pygame
   - pyautogui
   - keyboard


   ```bash
        pip install opencv-python numpy pygame pyautogui keyboard
   ```
2. Connect your camera from OBS and make sure it works.
3. Run the script
4. Use the P key to enable/disable the script.
5. Press Alt + P to exit.

## Settings
- Adjust parameters at the beginning of the file to fine-tune sensitivity, zone sizes, stability frame count, etc.

## Important
- Not all PCs support high frame rates (120 FPS). 
- The script works only with white and red zones.
- For correct operation, you need to configure OBS and zoom in on the center of the frame until the debug screen starts to detect the white area.

## Tech part
```bash
More FPS (120), filters and logick for colors, optimization, delete yellow color. 

Best Options:

   MIN_ZONE_WIDTH = 8
   MIN_ZONE_HEIGHT = 8
   MIN_CURSOR_WIDTH = 5
   MIN_CURSOR_HEIGHT = 5
   ZONE_DELAY_FRAMES = 3
   FRAME_DELAY = 1.0 / 120
   CURSOR_RADIUS = 5
   last_press_time = 0
   press_delay = 0.6

-OBS zoomed in webcam

-OBS filters:

Сolor correction
           1.00
          -1.60
          -0.0500
           0.00
           0.00 
           1.0000


COLORS:

RED 
	 lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 120, 120])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.bitwise_or(
        cv2.inRange(hsv, lower_red1, upper_red1),
        cv2.inRange(hsv, lower_red2, upper_red2)
    )

WHITE
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
```
---

Author: vat134 
