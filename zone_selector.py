"""
zone_selector.py
Lets the operator click points on the first frame of a video/feed to define
a free-form (non-rectangular) restricted zone. Points can be clicked in ANY
order - they're automatically sorted by angle around the shape's center so
the polygon never self-crosses. Saves it to zone.json so it persists across
runs.

Controls:
  Left click      -> add a point to the polygon (order doesn't matter)
  Right click     -> remove the last added point (undo)
  'z' / Backspace -> also remove the last added point (undo)
  Enter / 'c'     -> confirm and close the polygon (needs 3+ points)
  'r'             -> reset all points
  Esc             -> cancel without saving
"""

import cv2
import json
import os
import math

def sort_points_by_angle(points):
    if len(points) < 3:
        return points
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def select_zone(video_path, save_path="data/zone.json", display_size=(1280, 960)):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {video_path}")

    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Could not read first frame to draw zone on.")

    frame = cv2.resize(frame, display_size)
    raw_points = []

    def redraw():
        display = frame.copy()
        ordered = sort_points_by_angle(raw_points)

        for pt in raw_points:
            cv2.circle(display, pt, 5, (0, 0, 255), -1)

        if len(ordered) > 1:
            for i in range(len(ordered)):
                pt1 = ordered[i]
                pt2 = ordered[(i + 1) % len(ordered)]
                if i == len(ordered) - 1 and len(ordered) < 3:
                    continue
                cv2.line(display, pt1, pt2, (0, 255, 255), 2)

        cv2.putText(display, f"Points: {len(raw_points)}  |  Click anywhere, any order  |  z/Backspace/Right-click: undo  Enter: confirm",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow("Set Restricted Zone", display)

    def undo_last_point():
        if raw_points:
            raw_points.pop()
            redraw()

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            raw_points.append((x, y))
            redraw()
        elif event == cv2.EVENT_RBUTTONDOWN:
            undo_last_point()

    cv2.namedWindow("Set Restricted Zone")
    cv2.setMouseCallback("Set Restricted Zone", mouse_callback)
    redraw()

    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (13, ord('c')):
            if len(raw_points) >= 3:
                break
            else:
                print("Need at least 3 points to form a polygon.")
        elif key in (ord('z'), 8):
            undo_last_point()
        elif key == ord('r'):
            raw_points = []
            redraw()
        elif key == 27:
            cv2.destroyAllWindows()
            print("Zone selection cancelled.")
            return None

    cv2.destroyAllWindows()

    final_points = sort_points_by_angle(raw_points)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    zone_data = {
        "display_size": display_size,
        "polygon": final_points
    }
    with open(save_path, "w") as f:
        json.dump(zone_data, f, indent=2)

    print(f"Zone saved with {len(final_points)} points to {save_path}")
    return final_points


def load_zone(save_path="data/zone.json"):
    if not os.path.exists(save_path):
        return None
    with open(save_path, "r") as f:
        data = json.load(f)
    return [tuple(pt) for pt in data["polygon"]]


if __name__ == "__main__":
    video_path = "data/test1.mp4"
    select_zone(video_path, display_size=(1280, 960))
    