from ultralytics import YOLO
import cv2
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
# INPUT_MODE:
#   "single_video" | "single_image" | "video_folder" | "image_folder"
INPUT_MODE = "video_folder"

# dùng cho single_video hoặc single_image
SOURCE = "./sample2.mp4"

# dùng cho folder mode
SOURCE_FOLDER = r"C:\Users\PC\Automatic-License-Plate-Recognition-using-YOLOv8\video test1"

MODE = "entry"  # hiện tại batch test chủ yếu để detect/read, không dùng exit matching

BURST_SIZE = 5
TRIGGER_CONSEC_FRAMES = 1
CLEAR_TO_REARM = 8
SHOW_PREVIEW = False
STOP_AFTER_FIRST_EVENT = False

# tăng tốc batch test video
PROCESS_EVERY_N_FRAMES = 1   # chỉ xử lý mỗi N frame
MAX_FRAMES_PER_SOURCE = 0    # 0 = không giới hạn

# debug
DEBUG_OCR = False
WRITE_SESSION_LOG = False

SAVE_DIR = "captures"
FULL_DIR = os.path.join(SAVE_DIR, "full_frames")
CROP_DIR = os.path.join(SAVE_DIR, "plate_crops")
SESSIONS_CSV = os.path.join(SAVE_DIR, "parking_sessions.csv")
BATCH_RESULTS_CSV = os.path.join(SAVE_DIR, "batch_results.csv")

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

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


def in_trigger_zone(box, frame_shape):
    """
    Camera-only trigger zone:
    vehicle center must be inside the middle-lower region of the frame.
    """
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
    """
    Returns:
      triggered (bool), vehicles (list of [x1,y1,x2,y2,score,class_id])
    """
    detections = coco_model(frame)[0]
    vehicles = []

    for det in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det
        if int(class_id) in VEHICLE_CLASSES:
            vehicles.append([x1, y1, x2, y2, score, class_id])

    triggered = any(in_trigger_zone(v[:4], frame.shape) for v in vehicles)
    return triggered, vehicles


def crop_plate_for_ocr(frame, x1, y1, x2, y2):
    """
    Padding + upscale + grayscale + CLAHE + bilateral + adaptive threshold.
    """
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
    """
    Run ALPR on one frame and return the best candidate in that frame.
    Baseline logic:
      optional vehicle detection -> plate detection -> OCR on gray/thresh
    Vehicle match is optional now:
      - if matched to a vehicle: good
      - if not matched: still allow OCR on plate
    """
    vehicle_dets = coco_model(frame, conf=0.20)[0]
    vehicle_boxes = []

    for det in vehicle_dets.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det
        if int(class_id) in VEHICLE_CLASSES:
            vehicle_boxes.append([x1, y1, x2, y2, len(vehicle_boxes)])

    plates = license_plate_detector(frame, conf=0.05)[0]

    if DEBUG_OCR:
        print("vehicle_boxes:", len(vehicle_boxes))
        print("plate_boxes:", len(plates.boxes.data.tolist()))

    best = None

    for plate in plates.boxes.data.tolist():
        x1, y1, x2, y2, plate_score, class_id = plate

        # Optional vehicle match
        if vehicle_boxes:
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(plate, vehicle_boxes)
        else:
            xcar1, ycar1, xcar2, ycar2, car_id = 0, 0, 0, 0, -1

        # If no matched vehicle, still continue OCR on the plate
        if car_id == -1:
            xcar1, ycar1, xcar2, ycar2 = 0, 0, 0, 0

        plate_crop, gray, thresh = crop_plate_for_ocr(frame, x1, y1, x2, y2)
        if plate_crop is None:
            continue

        text_gray, score_gray = read_license_plate(gray)
        text_thresh, score_thresh = read_license_plate(thresh)

        score_gray = 0.0 if score_gray is None else score_gray
        score_thresh = 0.0 if score_thresh is None else score_thresh

        if DEBUG_OCR:
            print("gray:", text_gray, score_gray, "| thresh:", text_thresh, score_thresh)

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

        rank = (
            candidate["valid_format"],
            candidate["ocr_score"],
            candidate["plate_score"]
        )

        if best is None or rank > (
            best["valid_format"],
            best["ocr_score"],
            best["plate_score"]
        ):
            best = candidate

    return best


def choose_best_from_burst(candidates):
    """
    Pick the best result from the burst of 2-3 frames.
    Priority:
      1) valid VN-like plate
      2) OCR score
      3) plate detection score
    """
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


def ensure_sessions_csv():
    if not os.path.exists(SESSIONS_CSV):
        with open(SESSIONS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "session_id",
                    "plate_number",
                    "confidence",
                    "timestamp",
                    "vehicle_bbox",
                    "plate_bbox",
                    "full_image_path",
                    "plate_crop_path",
                    "status"
                ]
            )
            writer.writeheader()


def append_session_row(event):
    ensure_sessions_csv()
    file_exists = os.path.exists(SESSIONS_CSV)

    with open(SESSIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "session_id",
                "plate_number",
                "confidence",
                "timestamp",
                "vehicle_bbox",
                "plate_bbox",
                "full_image_path",
                "plate_crop_path",
                "status"
            ]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(event)


def save_event(best_result):
    """
    Save chosen frame + plate crop and return an event object.
    """
    session_id = make_session_id()
    timestamp = now_str()

    full_path = os.path.join(FULL_DIR, f"{session_id}_full.jpg")
    crop_path = os.path.join(CROP_DIR, f"{session_id}_plate.jpg")

    cv2.imwrite(full_path, best_result["frame"])
    cv2.imwrite(crop_path, best_result["plate_crop"])

    event = {
        "session_id": session_id,
        "plate_number": best_result["plate_text"],
        "confidence": round(best_result["ocr_score"], 4),
        "timestamp": timestamp,
        "vehicle_bbox": json.dumps(best_result["car_bbox"]),
        "plate_bbox": json.dumps(best_result["plate_bbox"]),
        "full_image_path": full_path,
        "plate_crop_path": crop_path,
        "status": "active"
    }

    if WRITE_SESSION_LOG:
        append_session_row(event)

    return event


def collect_sources():
    if INPUT_MODE in ("single_video", "single_image"):
        return [SOURCE]

    if not os.path.isdir(SOURCE_FOLDER):
        raise RuntimeError(f"Source folder not found: {SOURCE_FOLDER}")

    files = []
    for name in sorted(os.listdir(SOURCE_FOLDER)):
        full_path = os.path.join(SOURCE_FOLDER, name)
        if not os.path.isfile(full_path):
            continue

        ext = os.path.splitext(name)[1].lower()
        if INPUT_MODE == "video_folder" and ext in VIDEO_EXTS:
            files.append(full_path)
        elif INPUT_MODE == "image_folder" and ext in IMAGE_EXTS:
            files.append(full_path)

    return files


def is_image_file(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


def make_result_row(source_path, source_type, result=None, status="no_detection", frame_index=-1, runtime_sec=0.0):
    if result is None:
        return {
            "source_path": source_path,
            "source_type": source_type,
            "status": status,
            "plate_number": "",
            "confidence": 0.0,
            "valid_format": 0,
            "frame_index": frame_index,
            "runtime_sec": round(float(runtime_sec), 4),
            "plate_bbox": ""
        }

    return {
        "source_path": source_path,
        "source_type": source_type,
        "status": status,
        "plate_number": result["plate_text"],
        "confidence": round(float(result["ocr_score"]), 4),
        "valid_format": int(util.license_complies_format(result["plate_text"])),
        "frame_index": frame_index,
        "runtime_sec": round(float(runtime_sec), 4),
        "plate_bbox": json.dumps(result["plate_bbox"])
    }


def write_batch_results(rows):
    if not rows:
        return

    with open(BATCH_RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_path",
                "source_type",
                "status",
                "plate_number",
                "confidence",
                "valid_format",
                "frame_index",
                "runtime_sec",
                "plate_bbox"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)


def process_single_image(image_path):
    start_time = time.time()

    frame = cv2.imread(image_path)
    if frame is None:
        elapsed = time.time() - start_time
        return make_result_row(
            image_path,
            "image",
            None,
            status="read_failed",
            runtime_sec=elapsed
        )

    result = alpr_on_frame(frame)
    elapsed = time.time() - start_time

    if result is None:
        return make_result_row(
            image_path,
            "image",
            None,
            status="no_detection",
            runtime_sec=elapsed
        )

    save_event(result)
    return make_result_row(
        image_path,
        "image",
        result,
        status="detected",
        runtime_sec=elapsed
    )


def process_single_video(video_path):
    start_time = time.time()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        elapsed = time.time() - start_time
        return make_result_row(
            video_path,
            "video",
            None,
            status="open_failed",
            runtime_sec=elapsed
        )

    frame_index = 0
    candidates = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_index += 1

        if MAX_FRAMES_PER_SOURCE > 0 and frame_index > MAX_FRAMES_PER_SOURCE:
            break

        if PROCESS_EVERY_N_FRAMES > 1 and (frame_index % PROCESS_EVERY_N_FRAMES != 0):
            continue

        result = alpr_on_frame(frame)
        if result is not None:
            result["_frame_index"] = frame_index
            candidates.append(result)

    cap.release()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()

    elapsed = time.time() - start_time

    if not candidates:
        return make_result_row(
            video_path,
            "video",
            None,
            status="no_detection",
            frame_index=-1,
            runtime_sec=elapsed
        )

    best_result = max(
        candidates,
        key=lambda r: (
            r["valid_format"],
            r["ocr_score"],
            r["plate_score"]
        )
    )

    best_frame_index = best_result.get("_frame_index", -1)
    save_event(best_result)

    return make_result_row(
        video_path,
        "video",
        best_result,
        status="detected",
        frame_index=best_frame_index,
        runtime_sec=elapsed
    )


def main():
    total_start_time = time.time()

    sources = collect_sources()
    if not sources:
        raise RuntimeError("No input sources found.")

    rows = []

    for idx, path in enumerate(sources, start=1):
        print(f"\n[{idx}/{len(sources)}] Processing: {path}")

        if INPUT_MODE in ("single_image", "image_folder") or is_image_file(path):
            row = process_single_image(path)
        else:
            row = process_single_video(path)

        rows.append(row)

        print(
            f"status={row['status']} | "
            f"plate={row['plate_number']} | "
            f"conf={row['confidence']} | "
            f"time={row['runtime_sec']:.2f}s"
        )

    write_batch_results(rows)

    total = len(rows)
    detected = sum(1 for r in rows if r["status"] == "detected")
    valid = sum(1 for r in rows if r["valid_format"] == 1)

    total_elapsed = time.time() - total_start_time
    avg_time = total_elapsed / total if total > 0 else 0.0

    print("\n=== BATCH SUMMARY ===")
    print(f"Total sources: {total}")
    print(f"Detected: {detected}")
    print(f"Valid format: {valid}")
    print(f"Total folder time: {total_elapsed:.2f} seconds")
    print(f"Average time per source: {avg_time:.2f} seconds")
    print(f"Saved CSV: {BATCH_RESULTS_CSV}")

    


if __name__ == "__main__":
    main()