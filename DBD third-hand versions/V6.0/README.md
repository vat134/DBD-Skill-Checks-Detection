# DBD third-hand V6

This folder contains different versions of the script.
\*The code is not here just in case, so as not to violate GitHub policy.\*

## Versions

- **DBD-third-hand_V6.2.py**: This is the stable version. Recommended.

- **DBD-third-hand_V6.3.py**: This is an optimized version. It may offer better performance but could be less stable.

# Technical Highlights with Code Samples

## Geometric intersection
```bash
    def circle_rect_intersect(circle_center, radius, rect):
        cx, cy = circle_center
        rx, ry, rw, rh = rect
        nearest_x = max(rx, min(cx, rx + rw))
        nearest_y = max(ry, min(cy, ry + rh))
        dx = cx - nearest_x
        dy = cy - nearest_y
        return (dx * dx + dy * dy) <= (radius * radius)
```
Efficient check between cursor (circle) and detection zones (rectangles).

## Stability filtering
```bash
    white_zone_history = deque(maxlen=WHITE_ZONE_PERSISTENCE)

    def zone_similar(z1, z2, tol=15):
        return all(abs(a - b) <= tol for a, b in zip(z1, z2))
```
Uses history buffer and tolerance-based comparison to ignore flickering detections.

## Multithreaded frame capture
```bash
    def capture_thread():
        global shared_frame, stop_threads
        while not stop_threads:
            ret, frame = cap.read()
            if ret:
                with frame_lock:
                    shared_frame = frame.copy()

    threading.Thread(target=capture_thread, daemon=True).start()

```
Runs camera acquisition on a separate thread for stable FPS.

## Configurable parameters
```bash
    MIN_ZONE_WIDTH = 8
    MIN_CURSOR_HEIGHT = 5
    FRAME_DELAY = 1.0 / 120
    WHITE_ZONE_PERSISTENCE = 10
    ACTION_COOLDOWN = 0.6

```
All key detection and timing values grouped for easy tuning.

## Audio feedback
```bash
    def beep_toggle(on: bool):
        sound_file = SOUND_ON_PATH if on else SOUND_OFF_PATH
        sound = pygame.mixer.Sound(sound_file)
        sound.set_volume(0.1)
        sound.play()

```
Provides immediate sound feedback when script toggles.