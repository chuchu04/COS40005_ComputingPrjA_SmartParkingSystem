from ultralytics import YOLO
import cv2
import numpy as np
import os
import json
import time
import uuid
import csv
import util
from util import get_car, read_license_plate

# -----------------------------
# Config
# -----------------------------
SOURCE = "./sample2.mp4"   # 0 = webcam, or path to video
MODE = "exit"             # "entry" or "exit"

BURST_SIZE = 3
TRIGGER_CONSEC_FRAMES = 3
CLEAR_TO_REARM = 8
SHOW_PREVIEW = True
STOP_AFTER_FIRST_EVENT = True

SAVE_DIR = "captures"
FULL_DIR = os.path.join(SAVE_DIR, "full_frames")
CROP_DIR = os.path.join(SAVE_DIR, "plate_crops")
SESSIONS_CSV = os.path.join(SAVE_DIR, "parking_sessions.csv")

VEHICLE_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(CROP_DIR, exist_ok=True)

# -----------------------------
# Load models
# -----------------------------
coco_model = YOLO("yolov8n.pt")
license_plate_detector = YOLO("license_plate_detector.pt")


# -----------------------------
# Helpers
# -----------------------------
def now_str():
    return time.strftime("%Y%m%d_%H%M%S")


def make_session_id():
    return f"{MODE}_{now_str()}_{uuid.uuid4().hex[:6]}"


def ensure_sessions_csv():
    if not os.path.exists(SESSIONS_CSV):
        with open(SESSIONS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "session_id",
                    "plate_number",
                    "entry_time",
                    "exit_time",
                    "entry_confidence",
                    "exit_confidence",
                    "entry_full_image_path",
                    "exit_full_image_path",
                    "entry_plate_crop_path",
                    "exit_plate_crop_path",
                    "entry_vehicle_bbox",
                    "exit_vehicle_bbox",
                    "entry_plate_bbox",
                    "exit_plate_bbox",
                    "status"
                ]
            )
            writer.writeheader()


def read_sessions():
    ensure_sessions_csv()
    with open(SESSIONS_CSV, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_sessions(rows):
    with open(SESSIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "session_id",
                "plate_number",
                "entry_time",
                "exit_time",
                "entry_confidence",
                "exit_confidence",
                "entry_full_image_path",
                "exit_full_image_path",
                "entry_plate_crop_path",
                "exit_plate_crop_path",
                "entry_vehicle_bbox",
                "exit_vehicle_bbox",
                "entry_plate_bbox",
                "exit_plate_bbox",
                "status"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)


def save_images(best_result, session_id):
    full_path = os.path.join(FULL_DIR, f"{session_id}_full.jpg")
    crop_path = os.path.join(CROP_DIR, f"{session_id}_plate.jpg")

    cv2.imwrite(full_path, best_result["frame"])
    cv2.imwrite(crop_path, best_result["plate_crop"])

    return full_path, crop_path


def create_entry_session(best_result):
    rows = read_sessions()

    session_id = make_session_id()
    timestamp = now_str()
    full_path, crop_path = save_images(best_result, session_id)

    event = {
        "session_id": session_id,
        "plate_number": best_result["plate_text"],
        "entry_time": timestamp,
        "exit_time": "",
        "entry_confidence": round(best_result["ocr_score"], 4),
        "exit_confidence": "",
        "entry_full_image_path": full_path,
        "exit_full_image_path": "",
        "entry_plate_crop_path": crop_path,
        "exit_plate_crop_path": "",
        "entry_vehicle_bbox": json.dumps(best_result["car_bbox"]),
        "exit_vehicle_bbox": "",
        "entry_plate_bbox": json.dumps(best_result["plate_bbox"]),
        "exit_plate_bbox": "",
        "status": "active"
    }

    rows.append(event)
    write_sessions(rows)
    return event


def find_active_session_by_plate(plate_number):
    rows = read_sessions()
    for row in rows:
        if row["plate_number"] == plate_number and row["status"] == "active":
            return row["session_id"]
    return None


def update_exit_session(best_result):
    rows = read_sessions()

    plate_number = best_result["plate_text"]
    matched_id = find_active_session_by_plate(plate_number)

    timestamp = now_str()

    if matched_id is None:
        # no matching active session found
        session_id = make_session_id()
        full_path, crop_path = save_images(best_result, session_id)

        event = {
            "session_id": session_id,
            "plate_number": plate_number,
            "entry_time": "",
            "exit_time": timestamp,
            "entry_confidence": "",
            "exit_confidence": round(best_result["ocr_score"], 4),
            "entry_full_image_path": "",
            "exit_full_image_path": full_path,
            "entry_plate_crop_path": "",
            "exit_plate_crop_path": crop_path,
            "entry_vehicle_bbox": "",
            "exit_vehicle_bbox": json.dumps(best_result["car_bbox"]),
            "entry_plate_bbox": "",
            "exit_plate_bbox": json.dumps(best_result["plate_bbox"]),
            "status": "review"
        }

        rows.append(event)
        write_sessions(rows)
        return event, False

    # matched active entry -> close session
    for row in rows:
        if row["session_id"] == matched_id and row["status"] == "active":
            full_path, crop_path = save_images(best_result, matched_id + "_exit")
            row["exit_time"] = timestamp
            row["exit_confidence"] = round(best_result["ocr_score"], 4)
            row["exit_full_image_path"] = full_path
            row["exit_plate_crop_path"] = crop_path
            row["exit_vehicle_bbox"] = json.dumps(best_result["car_bbox"])
            row["exit_plate_bbox"] = json.dumps(best_result["plate_bbox"])
            row["status"] = "completed"
            write_sessions(rows)
            return row, True

    return None, False


def in_trigger_zone(box, frame_shape):
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    zone_x1 = int(w * 0.20)
    zone_x2 = int(w * 0.80)
    zone_y1 = int(h * 0.45)
    zone_y2 = h - 1

    return zone_x1 <= cx <= zone_x2 and zone_y1 <= cy <= zone_y2


def detect_trigger_vehicle(frame):
    detections = coco_model(frame)[0]
    vehicles = []

    for det in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det
        if int(class_id) in VEHICLE_CLASSES:
            vehicles.append([x1, y1, x2, y2, score, class_id])

    triggered = any(in_trigger_zone(v[:4], frame.shape) for v in vehicles)
    return triggered, vehicles


def crop_plate_for_ocr(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]

    pad_x = int((x2 - x1) * 0.10)
    pad_y = int((y2 - y1) * 0.18)

    cx1 = max(0, int(x1) - pad_x)
    cy1 = max(0, int(y1) - pad_y)
    cx2 = min(w, int(x2) + pad_x)
    cy2 = min(h, int(y2) + pad_y)

    if cx2 <= cx1 or cy2 <= cy1:
        return None, None, None

    plate_crop = frame[cy1:cy2, cx1:cx2, :]
    if plate_crop.size == 0:
        return None, None, None

    scale = 2.5
    plate_crop = cv2.resize(
        plate_crop,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC
    )

    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    gray = cv2.bilateralFilter(gray, 7, 50, 50)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    return plate_crop, gray, thresh


def alpr_on_frame(frame):
    vehicle_dets = coco_model(frame)[0]
    vehicle_boxes = []

    for det in vehicle_dets.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det
        if int(class_id) in VEHICLE_CLASSES:
            vehicle_boxes.append([x1, y1, x2, y2, len(vehicle_boxes)])

    if not vehicle_boxes:
        return None

    plates = license_plate_detector(frame)[0]
    best = None

    for plate in plates.boxes.data.tolist():
        x1, y1, x2, y2, plate_score, class_id = plate

        xcar1, ycar1, xcar2, ycar2, car_id = get_car(plate, vehicle_boxes)
        if car_id == -1:
            continue

        plate_crop, gray, thresh = crop_plate_for_ocr(frame, x1, y1, x2, y2)
        if plate_crop is None:
            continue

        text_gray, score_gray = read_license_plate(gray)
        text_thresh, score_thresh = read_license_plate(thresh)

        score_gray = 0.0 if score_gray is None else score_gray
        score_thresh = 0.0 if score_thresh is None else score_thresh

        if score_thresh >= score_gray:
            plate_text = text_thresh
            ocr_score = score_thresh
        else:
            plate_text = text_gray
            ocr_score = score_gray

        if plate_text is None:
            continue

        valid_format = 1 if util.license_complies_format(plate_text) else 0

        candidate = {
            "plate_text": plate_text,
            "ocr_score": float(ocr_score),
            "plate_score": float(plate_score),
            "valid_format": valid_format,
            "car_bbox": [float(xcar1), float(ycar1), float(xcar2), float(ycar2)],
            "plate_bbox": [float(x1), float(y1), float(x2), float(y2)],
            "plate_crop": plate_crop,
            "frame": frame.copy()
        }

        rank = (candidate["valid_format"], candidate["ocr_score"], candidate["plate_score"])
        if best is None or rank > (
            best["valid_format"], best["ocr_score"], best["plate_score"]
        ):
            best = candidate

    return best


def choose_best_from_burst(candidates):
    if not candidates:
        return None

    candidates = [c for c in candidates if c is not None]
    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (c["valid_format"], c["ocr_score"], c["plate_score"]),
        reverse=True
    )
    return candidates[0]


# -----------------------------
# Main gate loop
# -----------------------------
ensure_sessions_csv()

cap = cv2.VideoCapture(SOURCE)
if not cap.isOpened():
    raise RuntimeError("Could not open camera/video source.")

armed = True
trigger_count = 0
clear_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    triggered, vehicles = detect_trigger_vehicle(frame)

    if triggered:
        trigger_count += 1
        clear_count = 0
    else:
        clear_count += 1
        trigger_count = 0
        if clear_count >= CLEAR_TO_REARM:
            armed = True

    if SHOW_PREVIEW:
        h, w = frame.shape[:2]
        zx1, zx2 = int(w * 0.20), int(w * 0.80)
        zy1, zy2 = int(h * 0.45), h - 1
        cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), (0, 255, 255), 2)

        for v in vehicles:
            x1, y1, x2, y2, score, class_id = v
            color = (0, 255, 0) if in_trigger_zone(v[:4], frame.shape) else (255, 0, 0)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)

        status_text = f"Mode: {MODE} | Armed: {armed} | Trigger count: {trigger_count}"
        cv2.putText(frame, status_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    if armed and trigger_count >= TRIGGER_CONSEC_FRAMES:
        burst_frames = [frame.copy()]

        for _ in range(BURST_SIZE - 1):
            ret2, frame2 = cap.read()
            if not ret2:
                break
            burst_frames.append(frame2.copy())

        burst_results = []
        for burst_frame in burst_frames:
            res = alpr_on_frame(burst_frame)
            if res is not None:
                burst_results.append(res)

        best_result = choose_best_from_burst(burst_results)

        if best_result is not None:
            if MODE == "entry":
                event = create_entry_session(best_result)
                print("\n=== ENTRY EVENT ===")
                print(json.dumps(event, indent=2))
            elif MODE == "exit":
                event, matched = update_exit_session(best_result)
                if matched:
                    print("\n=== EXIT MATCHED ===")
                else:
                    print("\n=== EXIT NEEDS REVIEW ===")
                print(json.dumps(event, indent=2))

            print(f"\nSaved sessions log to: {SESSIONS_CSV}")

            if STOP_AFTER_FIRST_EVENT:
                break

        armed = False
        trigger_count = 0

    if SHOW_PREVIEW:
        cv2.imshow("Snapshot Gate ALPR", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()