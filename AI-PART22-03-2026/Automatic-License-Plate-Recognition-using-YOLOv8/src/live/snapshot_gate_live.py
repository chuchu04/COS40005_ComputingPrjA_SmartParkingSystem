from ultralytics import YOLO
import cv2
import os
import json
import time
import uuid
import csv
import numpy as np
from collections import deque

import util
from util import get_car, read_license_plate

# =========================================================
# LIVE / WEBCAM CONFIG
# =========================================================
SOURCE = 0                 # 0 = webcam mặc định, thử 1 nếu không mở đúng camera
MODE = "entry"
SHOW_PREVIEW = True
WRITE_SESSION_LOG = True
DEBUG_OCR = True

# Camera tuning
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
CAMERA_BUFFERSIZE = 1

USE_AUTOFOCUS = True
MANUAL_FOCUS = -1           # -1 = không ép manual focus

# Trigger / burst
TRIGGER_CONSEC_FRAMES = 1   # demo dễ hơn; tăng lên 2 nếu bị trigger quá nhạy
CLEAR_TO_REARM = 8
BURST_SIZE = 3
BURST_DELAY_MS = 40

# Delay trước khi chụp burst để bạn chỉnh vị trí điện thoại / xe
PRE_CAPTURE_DELAY_SECONDS = 2.0

# Demo / runtime control
STOP_AFTER_FIRST_EVENT = False
RESIZE_PREVIEW_WIDTH = 960
MAX_RUNTIME_SECONDS = 0     # 0 = chạy đến khi bấm q

# Detector confidence
VEHICLE_CONF = 0.20
PLATE_CONF = 0.08

# Preview overlay
DRAW_PLATE_BOX = True
DRAW_VEHICLE_BOX = True
DRAW_TRIGGER_ZONE = True
DRAW_LAST_RESULT = True

# Preview / banner
SHOW_STATUS_BANNER = True
RECORDED_BANNER_SECONDS = 3.0

# Cooldown after one recorded event
COOLDOWN_SECONDS = 2.5

# Debug clip save
SAVE_DEBUG_CLIP = False
PRE_EVENT_BUFFER_SEC = 1.5
POST_EVENT_FRAMES = 15
DEBUG_CLIP_FPS = 20

SAVE_DIR = "captures_live"
FULL_DIR = os.path.join(SAVE_DIR, "full_frames")
CROP_DIR = os.path.join(SAVE_DIR, "plate_crops")
DEBUG_CLIP_DIR = os.path.join(SAVE_DIR, "debug_clips")
SESSIONS_CSV = os.path.join(SAVE_DIR, "parking_sessions.csv")

VEHICLE_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(CROP_DIR, exist_ok=True)
os.makedirs(DEBUG_CLIP_DIR, exist_ok=True)

# =========================================================
# LOAD MODELS
# =========================================================
# Dùng detector cũ ổn định làm baseline live
coco_model = YOLO("yolov8n.pt")
license_plate_detector = YOLO("license_plate_detector.pt")


# =========================================================
# HELPERS
# =========================================================
def now_str():
    return time.strftime("%Y%m%d_%H%M%S")


def make_session_id():
    return f"{MODE}_{now_str()}_{uuid.uuid4().hex[:6]}"


def resize_for_preview(frame, target_width=1280):
    h, w = frame.shape[:2]
    if w <= target_width:
        return frame
    scale = target_width / float(w)
    new_h = int(h * scale)
    return cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)


def configure_camera(cap):
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFERSIZE)
    except Exception:
        pass

    try:
        if USE_AUTOFOCUS:
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        else:
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            if MANUAL_FOCUS >= 0:
                cap.set(cv2.CAP_PROP_FOCUS, MANUAL_FOCUS)
    except Exception:
        pass

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Camera actual settings: {actual_w}x{actual_h} @ {actual_fps:.1f} FPS")


def in_trigger_zone(box, frame_shape):
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    zone_x1, zone_y1, zone_x2, zone_y2 = get_trigger_zone_rect(frame_shape)
    return zone_x1 <= cx <= zone_x2 and zone_y1 <= cy <= zone_y2


def get_trigger_zone_rect(frame_shape):
    """
    Trigger zone / detection ROI rộng hơn cho case điện thoại đặt trên bàn:
    - ngang: 6% -> 94%
    - dọc: 22% -> 96%
    """
    h, w = frame_shape[:2]
    zone_x1 = int(w * 0.06)
    zone_x2 = int(w * 0.94)
    zone_y1 = int(h * 0.22)
    zone_y2 = int(h * 0.96)
    return zone_x1, zone_y1, zone_x2, zone_y2


def detect_trigger_vehicle(frame):
    """
    Detect xe CHỈ trong vùng trigger ROI.
    Cách này giúp:
    - xe trong màn hình điện thoại to hơn tương đối
    - trigger được từ khoảng cách xa hơn
    - chạy nhanh hơn vì không detect toàn khung hình
    """
    h, w = frame.shape[:2]
    rx1, ry1, rx2, ry2 = get_trigger_zone_rect(frame.shape)

    roi = frame[ry1:ry2, rx1:rx2]
    if roi is None or roi.size == 0:
        return False, []

    detections = coco_model(
        roi,
        conf=VEHICLE_CONF,
        classes=VEHICLE_CLASSES,
        verbose=False
    )[0]

    vehicles = []
    for det in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det

        # map bbox từ ROI về khung hình gốc
        x1 += rx1
        x2 += rx1
        y1 += ry1
        y2 += ry1

        vehicles.append([x1, y1, x2, y2, score, class_id])

    triggered = len(vehicles) > 0
    return triggered, vehicles


def _normalize_ocr_text(text):
    if text is None:
        return ""
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def _is_standard_vn_raw(raw):
    """
    Dạng chuẩn mục tiêu hiện tại:
    2 digits + 1 letter + 5 digits
    ví dụ: 51F57493
    """
    return (
        len(raw) == 8 and
        raw[:2].isdigit() and
        raw[2].isalpha() and
        raw[3:].isdigit()
    )


def _format_vn_raw(raw):
    """
    51F57493 -> 51F-574.93
    """
    if _is_standard_vn_raw(raw):
        return f"{raw[:3]}-{raw[3:6]}.{raw[6:]}"
    return raw


def _ocr_region_with_allowlist(region_img, allowlist=None):
    """
    OCR riêng cho vùng nhỏ.
    Ưu tiên dùng util.reader.readtext(..., allowlist=...)
    Nếu không được thì fallback sang read_license_plate().
    """
    if region_img is None or region_img.size == 0:
        return None, 0.0

    try:
        if hasattr(util, "reader"):
            results = util.reader.readtext(
                region_img,
                detail=1,
                paragraph=False,
                allowlist=allowlist
            )
            if results:
                best = max(results, key=lambda x: x[2])
                text = best[1]
                score = float(best[2])
                return text, score
    except Exception:
        pass

    text, score = read_license_plate(region_img)
    score = 0.0 if score is None else float(score)
    return text, score


def _build_region_variants(region_gray):
    """
    Nâng cấp mạnh hơn cho prefix/middle rescue:
    - upscale 3x
    - CLAHE
    - sharpen
    - adaptive threshold
    - otsu
    - otsu inverse
    - morphology close nhẹ
    """
    if region_gray is None or region_gray.size == 0:
        return {}

    up = cv2.resize(region_gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(up)

    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.8, blur, -0.8, 0)

    thresh = cv2.adaptiveThreshold(
        sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    _, otsu = cv2.threshold(
        sharp,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    _, otsu_inv = cv2.threshold(
        sharp,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    otsu = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)
    otsu_inv = cv2.morphologyEx(otsu_inv, cv2.MORPH_CLOSE, kernel)

    return {
        "gray": gray,
        "sharp": sharp,
        "thresh": thresh,
        "otsu": otsu,
        "otsu_inv": otsu_inv
    }


def _pick_best_region_candidate(candidates):
    """
    candidates: list of (text, score, variant_name)
    group + voting giống OCR full plate
    """
    if not candidates:
        return None, 0.0, {}

    grouped = {}
    for text, score, variant_name in candidates:
        key = str(text).strip().upper()
        if not key:
            continue

        if key not in grouped:
            grouped[key] = {
                "count": 0,
                "max_score": 0.0,
                "score_sum": 0.0,
                "variants": []
            }

        grouped[key]["count"] += 1
        grouped[key]["max_score"] = max(grouped[key]["max_score"], float(score))
        grouped[key]["score_sum"] += float(score)
        grouped[key]["variants"].append(variant_name)

    if not grouped:
        return None, 0.0, {}

    for key in grouped:
        grouped[key]["mean_score"] = grouped[key]["score_sum"] / grouped[key]["count"]

    ranked = sorted(
        grouped.items(),
        key=lambda item: (
            item[1]["count"],
            item[1]["max_score"],
            item[1]["mean_score"]
        ),
        reverse=True
    )

    best_key, best_info = ranked[0]
    return best_key, best_info["max_score"], grouped


def crop_plate_for_ocr(frame, x1, y1, x2, y2):
    """
    Crop plate với padding rộng hơn, upscale lớn hơn,
    và tạo nhiều biến thể ảnh cho OCR.
    Return:
        plate_crop, variants
    """
    h, w = frame.shape[:2]

    pad_x = int((x2 - x1) * 0.14)
    pad_y = int((y2 - y1) * 0.22)

    cx1 = max(0, int(x1) - pad_x)
    cy1 = max(0, int(y1) - pad_y)
    cx2 = min(w, int(x2) + pad_x)
    cy2 = min(h, int(y2) + pad_y)

    if cx2 <= cx1 or cy2 <= cy1:
        return None, None

    plate_crop = frame[cy1:cy2, cx1:cx2, :]
    if plate_crop is None or plate_crop.size == 0:
        return None, None

    scale = 4.0
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

    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.6, blur, -0.6, 0)

    thresh = cv2.adaptiveThreshold(
        sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    _, otsu = cv2.threshold(
        sharp,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    _, otsu_inv = cv2.threshold(
        sharp,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    variants = {
        "gray": gray,
        "sharp": sharp,
        "thresh": thresh,
        "otsu": otsu,
        "otsu_inv": otsu_inv
    }

    return plate_crop, variants


def read_prefix_digits_from_plate_crop(plate_crop):
    """
    Đọc riêng 2 số đầu của biển.
    """
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0, {}

    h, w = plate_crop.shape[:2]

    # ĐÚNG: crop vùng sát bên trái
    x1 = int(w * 0.00)
    x2 = int(w * 0.26)
    y1 = int(h * 0.08)
    y2 = int(h * 0.95)

    region = plate_crop[y1:y2, x1:x2]
    if region is None or region.size == 0:
        return None, 0.0, {}

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    variants = _build_region_variants(gray)

    candidates = []
    for variant_name, variant_img in variants.items():
        text, score = _ocr_region_with_allowlist(variant_img, allowlist="0123456789")
        score = 0.0 if score is None else float(score)

        cleaned = _normalize_ocr_text(text)
        digits = "".join(ch for ch in cleaned if ch.isdigit())

        if len(digits) >= 2:
            prefix = digits[:2]
            candidates.append((prefix, score, variant_name))

    best_prefix, best_score, grouped = _pick_best_region_candidate(candidates)
    return best_prefix, best_score, grouped


def read_middle_letter_from_plate_crop(plate_crop):
    """
    Đọc riêng ký tự chữ giữa.
    """
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0, {}

    h, w = plate_crop.shape[:2]

    # ĐÚNG: crop quanh vị trí chữ giữa
    x1 = int(w * 0.20)
    x2 = int(w * 0.40)
    y1 = int(h * 0.08)
    y2 = int(h * 0.95)

    region = plate_crop[y1:y2, x1:x2]
    if region is None or region.size == 0:
        return None, 0.0, {}

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    variants = _build_region_variants(gray)

    candidates = []
    for variant_name, variant_img in variants.items():
        text, score = _ocr_region_with_allowlist(variant_img, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        score = 0.0 if score is None else float(score)

        cleaned = _normalize_ocr_text(text)
        letters = "".join(ch for ch in cleaned if ch.isalpha())

        if len(letters) >= 1:
            middle = letters[0]
            candidates.append((middle, score, variant_name))

    best_middle, best_score, grouped = _pick_best_region_candidate(candidates)
    return best_middle, best_score, grouped


def apply_prefix_middle_rescue(
    base_text,
    prefix_digits,
    prefix_score,
    middle_letter,
    middle_score,
    prefix_min_score=0.40,
    middle_min_score=0.40
):
    """
    OCR full plate trước -> rescue prefix + middle sau.
    Chỉ thay nếu score đủ tốt.
    Return:
        rescued_text, changed
    """
    raw = _normalize_ocr_text(base_text)

    if len(raw) >= 8:
        raw = raw[:8]
    elif len(raw) == 7:
        if raw[:2].isdigit() and raw[2:].isdigit() and middle_letter and middle_score >= middle_min_score:
            raw = raw[:2] + middle_letter + raw[2:]
        else:
            return _format_vn_raw(raw), False
    else:
        return _format_vn_raw(raw), False

    chars = list(raw)
    changed = False

    if (
        prefix_digits is not None and len(prefix_digits) == 2 and
        prefix_score >= prefix_min_score and
        (chars[0] != prefix_digits[0] or chars[1] != prefix_digits[1])
    ):
        chars[0] = prefix_digits[0]
        chars[1] = prefix_digits[1]
        changed = True

    if (
        middle_letter is not None and len(middle_letter) == 1 and
        middle_score >= middle_min_score and
        chars[2] != middle_letter
    ):
        chars[2] = middle_letter
        changed = True

    rescued_raw = "".join(chars[:8])

    if _is_standard_vn_raw(rescued_raw):
        return _format_vn_raw(rescued_raw), changed

    return _format_vn_raw(raw), False


def alpr_on_frame(frame):
    """
    Detect vehicle + plate, rồi OCR full-plate multi-variant.
    KHÔNG dùng prefix rescue / middle rescue.
    Ưu tiên output ổn định cho live demo.
    """
    # chỉ detect vehicle classes, không lấy object khác
    vehicle_dets = coco_model(frame, conf=VEHICLE_CONF, classes=VEHICLE_CLASSES, verbose=False)[0]
    vehicle_boxes = []

    for det in vehicle_dets.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = det
        vehicle_boxes.append([x1, y1, x2, y2, len(vehicle_boxes)])

    # plate detector
    plates = license_plate_detector(frame, conf=PLATE_CONF, verbose=False)[0]

    if DEBUG_OCR:
        print("vehicle_boxes:", len(vehicle_boxes))
        print("plate_boxes:", len(plates.boxes.data.tolist()))

    best = None

    for plate in plates.boxes.data.tolist():
        x1, y1, x2, y2, plate_score, class_id = plate

        # vehicle match optional
        if vehicle_boxes:
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(plate, vehicle_boxes)
        else:
            xcar1, ycar1, xcar2, ycar2, car_id = 0, 0, 0, 0, -1

        if car_id == -1:
            xcar1, ycar1, xcar2, ycar2 = 0, 0, 0, 0

        plate_crop, variants = crop_plate_for_ocr(frame, x1, y1, x2, y2)
        if plate_crop is None or variants is None:
            continue

        # OCR full plate trên nhiều biến thể
        ocr_candidates = []
        for variant_name, variant_img in variants.items():
            text, score = read_license_plate(variant_img)
            score = 0.0 if score is None else float(score)

            if text is None:
                continue

            cleaned = _normalize_ocr_text(text)

            # nếu raw đúng pattern 8 ký tự thì format lại chuẩn
            if _is_standard_vn_raw(cleaned):
                key = _format_vn_raw(cleaned)
            else:
                key = str(text).strip().upper()

            ocr_candidates.append((key, score, variant_name))

            if DEBUG_OCR:
                print(f"{variant_name}: {key} | {score:.4f}")

        if not ocr_candidates:
            continue

        # group candidate để voting
        grouped = {}
        for text, score, variant_name in ocr_candidates:
            key = str(text).strip().upper()
            if not key:
                continue

            if key not in grouped:
                grouped[key] = {
                    "count": 0,
                    "max_score": 0.0,
                    "score_sum": 0.0,
                    "variants": [],
                    "best_text": key,
                    "valid_format": 1 if util.license_complies_format(key) else 0
                }

            grouped[key]["count"] += 1
            grouped[key]["max_score"] = max(grouped[key]["max_score"], score)
            grouped[key]["score_sum"] += score
            grouped[key]["variants"].append(variant_name)

        if not grouped:
            continue

        for key in grouped:
            grouped[key]["mean_score"] = grouped[key]["score_sum"] / grouped[key]["count"]

        # full OCR voting
        ranked = sorted(
            grouped.items(),
            key=lambda item: (
                item[1]["valid_format"],
                item[1]["count"],
                item[1]["max_score"],
                item[1]["mean_score"],
                float(plate_score)
            ),
            reverse=True
        )

        best_text, best_info = ranked[0]
        best_ocr_score = best_info["max_score"]
        valid_format = best_info["valid_format"]

        if DEBUG_OCR:
            print("FULL grouped:", grouped)
            print("FULL chosen:", best_text, best_ocr_score)

        candidate = {
            "plate_text": best_text,
            "ocr_score": float(best_ocr_score),
            "plate_score": float(plate_score),
            "valid_format": int(valid_format),
            "group_count": int(best_info["count"]),
            "car_bbox": [float(xcar1), float(ycar1), float(xcar2), float(ycar2)],
            "plate_bbox": [float(x1), float(y1), float(x2), float(y2)],
            "plate_crop": plate_crop,
            "frame": frame.copy()
        }

        # rank cuối cùng giữa các plate candidate
        rank = (
            candidate["valid_format"],
            candidate["group_count"],
            candidate["ocr_score"],
            candidate["plate_score"]
        )

        if best is None or rank > (
            best["valid_format"],
            best["group_count"],
            best["ocr_score"],
            best["plate_score"]
        ):
            best = candidate

    return best
def choose_best_from_burst(candidates):
    """
    Pick best result in burst:
      1) valid format
      2) OCR score
      3) plate score
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
                    "status",
                    "debug_clip_path"
                ]
            )
            writer.writeheader()


def append_session_row(event):
    ensure_sessions_csv()
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
                "status",
                "debug_clip_path"
            ]
        )
        writer.writerow(event)


def save_debug_clip(session_id, frames, fps=20):
    if not frames:
        return ""

    h, w = frames[0].shape[:2]
    clip_path = os.path.join(DEBUG_CLIP_DIR, f"{session_id}_debug.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(clip_path, fourcc, fps, (w, h))

    for fr in frames:
        if fr is not None and fr.size != 0:
            writer.write(fr)

    writer.release()
    return clip_path


def save_event(best_result, debug_frames=None):
    session_id = make_session_id()
    timestamp = now_str()

    full_path = os.path.join(FULL_DIR, f"{session_id}_full.jpg")
    crop_path = os.path.join(CROP_DIR, f"{session_id}_plate.jpg")

    cv2.imwrite(full_path, best_result["frame"])
    cv2.imwrite(crop_path, best_result["plate_crop"])

    debug_clip_path = ""
    if SAVE_DEBUG_CLIP and debug_frames:
        debug_clip_path = save_debug_clip(session_id, debug_frames, fps=DEBUG_CLIP_FPS)

    event = {
        "session_id": session_id,
        "plate_number": best_result["plate_text"],
        "confidence": round(best_result["ocr_score"], 4),
        "timestamp": timestamp,
        "vehicle_bbox": json.dumps(best_result["car_bbox"]),
        "plate_bbox": json.dumps(best_result["plate_bbox"]),
        "full_image_path": full_path,
        "plate_crop_path": crop_path,
        "status": "active",
        "debug_clip_path": debug_clip_path
    }

    if WRITE_SESSION_LOG:
        append_session_row(event)

    return event


def draw_preview(
    frame,
    vehicles,
    last_result=None,
    armed=True,
    trigger_count=0,
    last_text="",
    cooldown_remaining=0.0,
    banner_text="",
    banner_until=0.0,
    pending_capture_remaining=0.0
):
    out = frame.copy()
    now_t = time.time()

    if DRAW_TRIGGER_ZONE:
        zx1, zy1, zx2, zy2 = get_trigger_zone_rect(out.shape)
        cv2.rectangle(out, (zx1, zy1), (zx2, zy2), (0, 255, 255), 2)

    if DRAW_VEHICLE_BOX:
        for v in vehicles:
            x1, y1, x2, y2, score, class_id = v
            color = (0, 255, 0) if in_trigger_zone(v[:4], out.shape) else (255, 0, 0)
            cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            cv2.putText(
                out,
                f"veh {score:.2f}",
                (int(x1), max(20, int(y1) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

    if DRAW_PLATE_BOX and last_result is not None:
        px1, py1, px2, py2 = last_result["plate_bbox"]
        cv2.rectangle(out, (int(px1), int(py1)), (int(px2), int(py2)), (0, 0, 255), 2)

    line1 = f"Armed: {armed} | Trigger count: {trigger_count}"
    cv2.putText(
        out,
        line1,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2
    )

    if pending_capture_remaining > 0:
        cv2.putText(
            out,
            f"Capturing in: {pending_capture_remaining:.1f}s",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2
        )
    elif cooldown_remaining > 0:
        cv2.putText(
            out,
            f"Cooldown: {cooldown_remaining:.1f}s",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 165, 255),
            2
        )
    elif DRAW_LAST_RESULT and last_text:
        cv2.putText(
            out,
            f"Last plate: {last_text}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2
        )

    cv2.putText(
        out,
        "Press Q to quit",
        (20, out.shape[0] - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    if SHOW_STATUS_BANNER and banner_text and now_t < banner_until:
        cv2.rectangle(out, (20, 100), (min(out.shape[1] - 20, 900), 160), (0, 128, 0), -1)
        cv2.putText(
            out,
            banner_text,
            (35, 142),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

    return resize_for_preview(out, RESIZE_PREVIEW_WIDTH)


# =========================================================
# LIVE MAIN LOOP
# =========================================================
def main():
    if WRITE_SESSION_LOG:
        ensure_sessions_csv()

    cap = cv2.VideoCapture(SOURCE, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera source: {SOURCE}")

    configure_camera(cap)

    start_time = time.time()
    armed = True
    trigger_count = 0
    clear_count = 0
    last_event = None
    last_plate_text = ""
    total_events = 0

    cooldown_until = 0.0
    banner_text = ""
    banner_until = 0.0

    pending_capture = False
    pending_capture_until = 0.0

    pre_event_maxlen = max(1, int(PRE_EVENT_BUFFER_SEC * DEBUG_CLIP_FPS))
    pre_event_frames = deque(maxlen=pre_event_maxlen)

    print("=== SNAPSHOT GATE LIVE STARTED ===")
    print(f"SOURCE={SOURCE}")
    print("Press 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera frame read failed.")
            break

        now_t = time.time()

        if MAX_RUNTIME_SECONDS > 0 and (now_t - start_time) > MAX_RUNTIME_SECONDS:
            print("Max runtime reached.")
            break

        if SAVE_DEBUG_CLIP:
            pre_event_frames.append(frame.copy())

        # cooldown phase
        cooldown_remaining = max(0.0, cooldown_until - now_t)
        if cooldown_remaining > 0:
            if SHOW_PREVIEW:
                preview = draw_preview(
                    frame,
                    vehicles=[],
                    last_result=last_event,
                    armed=False,
                    trigger_count=0,
                    last_text=last_plate_text,
                    cooldown_remaining=cooldown_remaining,
                    banner_text=banner_text,
                    banner_until=banner_until,
                    pending_capture_remaining=0.0
                )
                cv2.imshow("Snapshot Gate Live", preview)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
            continue

        # countdown trước khi capture burst
        pending_capture_remaining = max(0.0, pending_capture_until - now_t)
        if pending_capture and pending_capture_remaining > 0:
            if SHOW_PREVIEW:
                preview = draw_preview(
                    frame,
                    [],
                    last_result=last_event,
                    armed=False,
                    trigger_count=0,
                    last_text=last_plate_text,
                    cooldown_remaining=0.0,
                    banner_text=banner_text,
                    banner_until=banner_until,
                    pending_capture_remaining=pending_capture_remaining
                )
                cv2.imshow("Snapshot Gate Live", preview)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
            continue

        # countdown hết thì chụp burst ngay
        if pending_capture and pending_capture_remaining <= 0:
            pending_capture = False

            burst_frames = [frame.copy()]

            for _ in range(BURST_SIZE - 1):
                if BURST_DELAY_MS > 0:
                    time.sleep(BURST_DELAY_MS / 1000.0)

                ret2, frame2 = cap.read()
                if not ret2:
                    break

                if SAVE_DEBUG_CLIP:
                    pre_event_frames.append(frame2.copy())

                burst_frames.append(frame2.copy())

            burst_results = []
            for burst_frame in burst_frames:
                res = alpr_on_frame(burst_frame)
                if res is not None:
                    burst_results.append(res)

            best_result = choose_best_from_burst(burst_results)

            if best_result is not None:
                debug_frames = []
                if SAVE_DEBUG_CLIP:
                    debug_frames.extend(list(pre_event_frames))
                    debug_frames.extend(burst_frames)

                    for _ in range(POST_EVENT_FRAMES):
                        ret3, frame3 = cap.read()
                        if not ret3:
                            break
                        debug_frames.append(frame3.copy())

                event = save_event(best_result, debug_frames=debug_frames)
                last_event = best_result
                last_plate_text = event["plate_number"]
                total_events += 1

                banner_text = f"RECORDED: {event['plate_number']}"
                banner_until = time.time() + RECORDED_BANNER_SECONDS
                cooldown_until = time.time() + COOLDOWN_SECONDS

                print("\n=== LIVE EVENT DETECTED ===")
                print(json.dumps(event, indent=2))

                if STOP_AFTER_FIRST_EVENT:
                    break
            else:
                if DEBUG_OCR:
                    print("Countdown finished but no valid burst result.")

            clear_count = 0
            trigger_count = 0
            armed = False
            continue

        triggered, vehicles = detect_trigger_vehicle(frame)

        if triggered:
            trigger_count += 1
            clear_count = 0
        else:
            clear_count += 1
            trigger_count = 0
            if clear_count >= CLEAR_TO_REARM:
                armed = True

        # vừa trigger đủ thì KHÔNG chụp ngay; bắt đầu countdown
        if armed and trigger_count >= TRIGGER_CONSEC_FRAMES and not pending_capture:
            pending_capture = True
            pending_capture_until = time.time() + PRE_CAPTURE_DELAY_SECONDS
            armed = False
            trigger_count = 0

        if SHOW_PREVIEW:
            preview = draw_preview(
                frame,
                vehicles,
                last_result=last_event,
                armed=armed and (not pending_capture),
                trigger_count=trigger_count,
                last_text=last_plate_text,
                cooldown_remaining=0.0,
                banner_text=banner_text,
                banner_until=banner_until,
                pending_capture_remaining=max(0.0, pending_capture_until - time.time()) if pending_capture else 0.0
            )
            cv2.imshow("Snapshot Gate Live", preview)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    cap.release()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()

    print("\n=== SNAPSHOT GATE LIVE STOPPED ===")
    print(f"Total events: {total_events}")


if __name__ == "__main__":
    main()