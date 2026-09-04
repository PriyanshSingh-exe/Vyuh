from ultralytics import YOLO
import cv2
import csv
import os
import numpy as np
import torch
import logging
from zone_selector import load_zone, select_zone

log_dir = "data/logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "system.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("vyuh")

DEVICE = 0 if torch.cuda.is_available() else "cpu"
USE_HALF = torch.cuda.is_available()
logger.info(f"Using device: {'GPU' if DEVICE == 0 else 'CPU'} | half precision: {USE_HALF}")

model = YOLO("yolo11m.pt")
if USE_HALF:
    model.half()

video_path = "test1.mp4"
local_output_path = "/content/output_detected.mp4"
output_path = "data/output_detected.mp4"
log_path = "data/alert_log.csv"
snapshots_dir = "data/snapshots"
zone_path = "data/zone.json"

os.makedirs(snapshots_dir, exist_ok=True)

CONFIDENCE_THRESHOLD = 0.5
ALERTABLE_LABELS = ["person", "car", "truck", "bus", "motorcycle", "bicycle"]

REALERT_COOLDOWN_SEC = 10
DETECT_EVERY_N_FRAMES = 2

MAX_WIDTH = 1280

probe_cap = cv2.VideoCapture(video_path)
if not probe_cap.isOpened():
    raise RuntimeError(f"Could not open video source: {video_path}")
native_width = int(probe_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
native_height = int(probe_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
probe_cap.release()

if native_width > MAX_WIDTH:
    scale = MAX_WIDTH / native_width
    width = MAX_WIDTH
    height = int(native_height * scale)
else:
    width, height = native_width, native_height

logger.info(f"Native resolution: {native_width}x{native_height} -> using {width}x{height}")

zone_polygon = load_zone(zone_path)
if zone_polygon is None:
    logger.info("No saved zone found. Let's configure one now.")
    zone_polygon = select_zone(video_path, save_path=zone_path, display_size=(width, height))
    if zone_polygon is None:
        raise SystemExit("Zone selection was cancelled. Exiting.")

zone_np = np.array(zone_polygon, dtype=np.int32)


def box_in_zone(box, polygon):
    x1, y1, x2, y2 = box
    foot_point = (int((x1 + x2) / 2), int(y2))
    result = cv2.pointPolygonTest(polygon, foot_point, False)
    return result >= 0, foot_point


cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    logger.error("Could not open video.")
else:
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
    cooldown_frames = int(REALERT_COOLDOWN_SEC * fps)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(local_output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        raise RuntimeError("Could not open VideoWriter. Check output_path and codecs available.")

    log_file = open(log_path, mode='w', newline='')
    log_writer = csv.writer(log_file)
    log_writer.writerow(["frame", "timestamp_sec", "track_id", "label", "confidence", "event", "snapshot_file"])

    logger.info("Processing video with polygon zone-intrusion alerts + ID tracking + logging...")

    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    alert_count = 0

    track_state = {}
    last_boxes = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        timestamp_sec = frame_count / fps

        run_detection = (frame_count % DETECT_EVERY_N_FRAMES == 0) or frame_count == 1

        if run_detection:
            results = model.track(frame, persist=True, tracker="botsort_custom.yaml",
                                   verbose=False, imgsz=640, device=DEVICE)
            last_boxes = results[0].boxes

        alert_this_frame = False
        seen_ids_this_frame = set()

        for box in last_boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])
            track_id = int(box.id[0]) if box.id is not None else -1

            if label not in ALERTABLE_LABELS or conf < CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            inside_zone, foot_point = box_in_zone((x1, y1, x2, y2), zone_np)
            id_label = f"ID:{track_id}" if track_id != -1 else "ID:?"

            if track_id != -1:
                seen_ids_this_frame.add(track_id)

            if inside_zone:
                alert_this_frame = True
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.circle(frame, foot_point, 4, (0, 0, 255), -1)
                cv2.putText(frame, f"ALERT: {label} {id_label} {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                if run_detection:
                    should_log = False
                    event_type = ""

                    if track_id == -1:
                        should_log = frame_count % 15 == 0
                        event_type = "detected"
                    else:
                        state = track_state.get(track_id)
                        if state is None or not state["in_zone"]:
                            should_log = True
                            event_type = "entered_zone"
                        else:
                            frames_since_last = frame_count - state["last_alert_frame"]
                            if frames_since_last >= cooldown_frames:
                                should_log = True
                                event_type = "still_present"

                        track_state[track_id] = {"in_zone": True, "last_alert_frame": frame_count}

                    if should_log:
                        alert_count += 1
                        snapshot_name = f"alert_{alert_count}_id{track_id}_frame{frame_count}.jpg"
                        snapshot_path = os.path.join(snapshots_dir, snapshot_name)
                        cv2.imwrite(snapshot_path, frame)
                        log_writer.writerow([frame_count, f"{timestamp_sec:.2f}", track_id, label,
                                              f"{conf:.2f}", event_type, snapshot_name])
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{label} {id_label} {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                if run_detection and track_id != -1 and track_id in track_state:
                    track_state[track_id]["in_zone"] = False

        if run_detection and frame_count % 300 == 0:
            stale_ids = [tid for tid in track_state if tid not in seen_ids_this_frame
                         and frame_count - track_state[tid]["last_alert_frame"] > 300]
            for tid in stale_ids:
                del track_state[tid]

        zone_color = (0, 0, 255) if alert_this_frame else (0, 165, 255)
        cv2.polylines(frame, [zone_np], isClosed=True, color=zone_color, thickness=2)
        cv2.putText(frame, "RESTRICTED ZONE", tuple(zone_np[0]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 2)

        out.write(frame)

        if frame_count % 30 == 0:
            logger.info(f"Processed {frame_count}/{total_frames} frames...")

    cap.release()
    out.release()
    log_file.close()

    import shutil
    shutil.copy(local_output_path, output_path)

    logger.info(f"Done! Video saved to {output_path}")
    logger.info(f"Alert log saved to {log_path}")
    logger.info(f"Snapshots saved to {snapshots_dir}")
    logger.info(f"Total logged alerts: {alert_count}")
    