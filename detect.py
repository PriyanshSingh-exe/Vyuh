from ultralytics import YOLO
import cv2
import csv
import os

model = YOLO("yolo11m.pt")

video_path = "data/test1.mp4"
output_path = "data/output_detected.mp4"
log_path = "data/alert_log.csv"
snapshots_dir = "data/snapshots"

os.makedirs(snapshots_dir, exist_ok=True)

CONFIDENCE_THRESHOLD = 0.5
ALERTABLE_LABELS = ["person", "car", "truck", "bus", "motorcycle", "bicycle"]

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
else:
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width, height = 960, 540

    zone_x1, zone_y1 = int(width * 0.20), int(height * 0.15)
    zone_x2, zone_y2 = int(width * 0.80), int(height * 0.90)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    log_file = open(log_path, mode='w', newline='')
    log_writer = csv.writer(log_file)
    log_writer.writerow(["frame", "timestamp_sec", "label", "confidence", "snapshot_file"])

    print("Processing video with zone-intrusion alerts + logging...")

    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    alert_count = 0

    def boxes_overlap(box1, box2):
        x1, y1, x2, y2 = box1
        zx1, zy1, zx2, zy2 = box2
        return not (x2 < zx1 or x1 > zx2 or y2 < zy1 or y1 > zy2)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        frame = cv2.resize(frame, (width, height))
        timestamp_sec = frame_count / fps

        results = model(frame, verbose=False, imgsz=640)

        alert_this_frame = False

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])

            if label not in ALERTABLE_LABELS or conf < CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            if boxes_overlap((x1, y1, x2, y2), (zone_x1, zone_y1, zone_x2, zone_y2)):
                alert_this_frame = True
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, f"ALERT: {label} {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                if frame_count % 15 == 0:
                    alert_count += 1
                    snapshot_name = f"alert_{alert_count}_frame{frame_count}.jpg"
                    snapshot_path = os.path.join(snapshots_dir, snapshot_name)
                    cv2.imwrite(snapshot_path, frame)

                    log_writer.writerow([frame_count, f"{timestamp_sec:.2f}", label, f"{conf:.2f}", snapshot_name])
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        zone_color = (0, 0, 255) if alert_this_frame else (0, 165, 255)
        cv2.rectangle(frame, (zone_x1, zone_y1), (zone_x2, zone_y2), zone_color, 2)
        cv2.putText(frame, "RESTRICTED ZONE", (zone_x1, zone_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 2)

        out.write(frame)

        if frame_count % 10 == 0:
            print(f"Processed {frame_count}/{total_frames} frames...")

    cap.release()
    out.release()
    log_file.close()
    print(f"Done! Video saved to {output_path}")
    print(f"Alert log saved to {log_path}")
    print(f"Snapshots saved to {snapshots_dir}")
    print(f"Total logged alerts: {alert_count}")
    