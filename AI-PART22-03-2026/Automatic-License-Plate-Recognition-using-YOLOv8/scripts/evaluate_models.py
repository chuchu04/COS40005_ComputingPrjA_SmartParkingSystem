import os
import csv
import json
import time
import cv2
from ultralytics import YOLO
import util
from util import (
    read_license_plate,
    read_middle_letter,
    read_prefix_digits,
    read_suffix_digits,
)

# =========================================================
# CONFIG
# =========================================================
IMAGE_DIR = r"C:\Users\PC\Automatic-License-Plate-Recognition-using-YOLOv8\test_eval\images"
LABELS_CSV = os.path.join(IMAGE_DIR, "labels.csv")

# choose: "pt" or "engine"
MODEL_BACKEND = "pt"

PLATE_MODEL_PATHS = {
    "pt": "license_plate_detector.pt",
    "engine": "license_plate_detector.engine",
}

# Gate ROI ratios: (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
# Tune if needed for your camera/view.
GATE_ROI = (0.18, 0.38, 0.82, 0.92)

# Output files
DETAILS_OUT = f"evaluation_details_gate_{MODEL_BACKEND}.csv"
SUMMARY_OUT = f"evaluation_summary_gate_{MODEL_BACKEND}.csv"

# Save crops/frames for failed cases
SAVE_BAD_CASE_CROPS = True
BAD_CASES_DIR = f"bad_cases_{MODEL_BACKEND}"


# =========================================================
# BASIC HELPERS
# =========================================================
def load_labels(path):
    labels = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            true_plate = row.get("true_plate", "").strip().upper()
            vehicle_type = row.get("vehicle_type", "").strip().lower()
            test_group = row.get("test_group", "").strip().lower()

            if filename and true_plate:
                labels.append(
                    {
                        "filename": filename,
                        "true_plate": true_plate,
                        "vehicle_type": vehicle_type,
                        "test_group": test_group,
                    }
                )
    return labels


def normalize_plate_key(text):
    if text is None:
        return ""
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def format_vn_car_plate_from_key(key):
    key = normalize_plate_key(key)
    if len(key) == 8 and key[:2].isdigit() and key[2].isalpha() and key[3:].isdigit():
        return f"{key[:3]}-{key[3:6]}.{key[6:]}"
    return key


def candidate_pattern_score(text):
    key = normalize_plate_key(text)

    if util.license_complies_format(text):
        return 4
    if len(key) == 8 and key[:2].isdigit() and key[2].isalpha() and key[3:].isdigit():
        return 3
    if len(key) == 8 and key[:2].isdigit() and key[2].isdigit() and key[3:].isdigit():
        return 2
    if len(key) == 9:
        return 1
    return 0


def choose_best_ocr_candidate(candidates):
    if not candidates:
        return None, 0.0, 0, {}

    grouped = {}

    for text, score in candidates:
        key = normalize_plate_key(text)
        if not key:
            continue

        if key not in grouped:
            grouped[key] = {
                "texts": [],
                "count": 0,
                "max_score": 0.0,
                "score_sum": 0.0,
                "valid_format": 0,
            }

        grouped[key]["texts"].append(text)
        grouped[key]["count"] += 1
        grouped[key]["max_score"] = max(grouped[key]["max_score"], float(score))
        grouped[key]["score_sum"] += float(score)

    if not grouped:
        return None, 0.0, 0, {}

    for key in grouped:
        valid_any = 0
        for t in grouped[key]["texts"]:
            if util.license_complies_format(t):
                valid_any = 1
                break

        grouped[key]["valid_format"] = valid_any
        grouped[key]["mean_score"] = grouped[key]["score_sum"] / grouped[key]["count"]

        valid_texts = [t for t in grouped[key]["texts"] if util.license_complies_format(t)]
        if valid_texts:
            grouped[key]["best_text"] = valid_texts[0]
        else:
            grouped[key]["best_text"] = grouped[key]["texts"][0]

        grouped[key]["pattern_score"] = candidate_pattern_score(grouped[key]["best_text"])

    ranked = sorted(
        grouped.items(),
        key=lambda item: (
            item[1]["valid_format"],
            item[1]["pattern_score"],
            item[1]["count"],
            item[1]["max_score"],
            item[1]["mean_score"],
        ),
        reverse=True,
    )

    _, best_info = ranked[0]
    return best_info["best_text"], best_info["max_score"], best_info["count"], grouped


# =========================================================
# ROI / CROP HELPERS
# =========================================================
def get_gate_roi(frame_shape):
    h, w = frame_shape[:2]
    rx1, ry1, rx2, ry2 = GATE_ROI
    x1 = int(w * rx1)
    y1 = int(h * ry1)
    x2 = int(w * rx2)
    y2 = int(h * ry2)
    return x1, y1, x2, y2


def crop_to_gate_roi(frame):
    x1, y1, x2, y2 = get_gate_roi(frame.shape)
    roi = frame[y1:y2, x1:x2].copy()
    return roi, (x1, y1, x2, y2)


def remap_bbox_from_roi(bbox, roi_offset):
    ox1, oy1, _, _ = roi_offset
    x1, y1, x2, y2 = bbox
    return [x1 + ox1, y1 + oy1, x2 + ox1, y2 + oy1]


def plate_sharpness_score(gray_img):
    if gray_img is None or gray_img.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray_img, cv2.CV_64F).var())


def safe_ratio_crop(img, x1r, x2r, y1r=0.10, y2r=0.90):
    h, w = img.shape[:2]
    x1 = max(0, int(w * x1r))
    x2 = min(w, int(w * x2r))
    y1 = max(0, int(h * y1r))
    y2 = min(h, int(h * y2r))
    crop = img[y1:y2, x1:x2]
    return crop


def get_plate_segments(plate_crop):
    if plate_crop is None or plate_crop.size == 0:
        return None, None, None, None

    full_plate_crop = plate_crop.copy()
    prefix_crop = safe_ratio_crop(plate_crop, 0.03, 0.30, 0.10, 0.90)
    middle_crop = safe_ratio_crop(plate_crop, 0.30, 0.44, 0.10, 0.90)
    suffix_crop = safe_ratio_crop(plate_crop, 0.44, 0.98, 0.10, 0.90)

    return full_plate_crop, prefix_crop, middle_crop, suffix_crop


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

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    return plate_crop, gray, thresh


# =========================================================
# RESCUE HELPERS
# =========================================================
def reconstruct_plate_from_segments(prefix_digits, middle_char, suffix_digits):
    if prefix_digits is None or middle_char is None or suffix_digits is None:
        return None

    prefix_digits = "".join(ch for ch in str(prefix_digits) if ch.isdigit())
    middle_char = "".join(ch for ch in str(middle_char).upper() if ch.isalpha())
    suffix_digits = "".join(ch for ch in str(suffix_digits) if ch.isdigit())

    if len(prefix_digits) != 2:
        return None
    if len(middle_char) < 1:
        return None
    if len(suffix_digits) != 5:
        return None

    key = prefix_digits + middle_char[0] + suffix_digits
    formatted = format_vn_car_plate_from_key(key)

    if util.license_complies_format(formatted):
        return formatted

    return None


def rescue_middle_letter_from_plate_crop(raw_text, plate_crop):
    if plate_crop is None or plate_crop.size == 0:
        return raw_text, 0.0

    key = normalize_plate_key(raw_text)

    if len(key) != 8:
        return raw_text, 0.0
    if not key[:2].isdigit():
        return raw_text, 0.0
    if not key[2].isdigit():
        return raw_text, 0.0
    if not key[3:].isdigit():
        return raw_text, 0.0

    middle_crop = safe_ratio_crop(plate_crop, 0.24, 0.36, 0.10, 0.90)
    if middle_crop is None or middle_crop.size == 0:
        return raw_text, 0.0

    middle_char, middle_score = read_middle_letter(middle_crop)

    if middle_char is None or middle_score < 0.85:
        return raw_text, 0.0

    rescued_key = key[:2] + middle_char + key[3:]
    rescued_text = format_vn_car_plate_from_key(rescued_key)

    if util.license_complies_format(rescued_text):
        return rescued_text, float(middle_score)

    return raw_text, 0.0


def rescue_prefix_digits_from_plate_crop(raw_text, plate_crop):
    if plate_crop is None or plate_crop.size == 0:
        return raw_text, 0.0

    key = normalize_plate_key(raw_text)

    if len(key) != 8:
        return raw_text, 0.0
    if not key[:2].isdigit():
        return raw_text, 0.0
    if not key[2].isalpha():
        return raw_text, 0.0
    if not key[3:].isdigit():
        return raw_text, 0.0

    prefix_crop = safe_ratio_crop(plate_crop, 0.04, 0.24, 0.10, 0.90)
    if prefix_crop is None or prefix_crop.size == 0:
        return raw_text, 0.0

    prefix_digits, prefix_score = read_prefix_digits(prefix_crop)

    if prefix_digits is None or len(prefix_digits) != 2 or prefix_score < 0.80:
        return raw_text, 0.0

    rescued_key = prefix_digits + key[2:]
    rescued_text = format_vn_car_plate_from_key(rescued_key)

    if util.license_complies_format(rescued_text):
        return rescued_text, float(prefix_score)

    return raw_text, 0.0


def rescue_plate_from_segments(raw_text, plate_crop):
    if plate_crop is None or plate_crop.size == 0:
        return raw_text, 0.0

    prefix_crop = safe_ratio_crop(plate_crop, 0.04, 0.24, 0.10, 0.90)
    middle_crop = safe_ratio_crop(plate_crop, 0.24, 0.36, 0.10, 0.90)
    suffix_crop = safe_ratio_crop(plate_crop, 0.36, 0.96, 0.10, 0.90)

    if prefix_crop.size == 0 or middle_crop.size == 0 or suffix_crop.size == 0:
        return raw_text, 0.0

    prefix_digits, prefix_score = read_prefix_digits(prefix_crop)
    middle_char, middle_score = read_middle_letter(middle_crop)
    suffix_digits, suffix_score = read_suffix_digits(suffix_crop)

    print("SEGMENT OCR:")
    print("  prefix_digits =", prefix_digits, "score =", prefix_score)
    print("  middle_char   =", middle_char, "score =", middle_score)
    print("  suffix_digits =", suffix_digits, "score =", suffix_score)

    if prefix_digits is None or prefix_score < 0.75:
        return raw_text, 0.0
    if middle_char is None or middle_score < 0.80:
        return raw_text, 0.0
    if suffix_digits is None or suffix_score < 0.75:
        return raw_text, 0.0

    rescued_text = reconstruct_plate_from_segments(prefix_digits, middle_char, suffix_digits)
    print("  reconstructed =", rescued_text)
    if rescued_text is None:
        return raw_text, 0.0
    
    segment_score = min(float(prefix_score), float(middle_score), float(suffix_score))
    return rescued_text, segment_score


# =========================================================
# MAIN IMAGE ALPR
# =========================================================
def alpr_on_image(frame, plate_model):
    roi, roi_offset = crop_to_gate_roi(frame)
    plate_results = plate_model(roi)[0]

    best = None

    for plate in plate_results.boxes.data.tolist():
        x1, y1, x2, y2, plate_score, class_id = plate

        full_plate_bbox = remap_bbox_from_roi([x1, y1, x2, y2], roi_offset)
        fx1, fy1, fx2, fy2 = full_plate_bbox

        plate_crop, gray, thresh = crop_plate_for_ocr(frame, fx1, fy1, fx2, fy2)
        if plate_crop is None:
            continue

        sharp = cv2.GaussianBlur(gray, (0, 0), 1.0)
        sharp = cv2.addWeighted(gray, 1.5, sharp, -0.5, 0)
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        variants = [
            ("gray", gray),
            ("sharp", sharp),
            ("thresh", thresh),
            ("otsu", otsu),
        ]

        ocr_candidates = []

        for _, variant in variants:
            text, score = read_license_plate(variant)
            score = 0.0 if score is None else score
            if text is not None:
                ocr_candidates.append((text, score))

        best_text, best_ocr_score, best_support, grouped_debug = choose_best_ocr_candidate(ocr_candidates)

        if best_text is None:
            continue

        rescued_text, rescue_score = rescue_middle_letter_from_plate_crop(best_text, plate_crop)
        if rescued_text != best_text:
            best_text = rescued_text
            best_ocr_score = max(float(best_ocr_score), float(rescue_score))

        rescued_prefix_text, prefix_rescue_score = rescue_prefix_digits_from_plate_crop(best_text, plate_crop)
        if rescued_prefix_text != best_text:
            best_text = rescued_prefix_text
            best_ocr_score = max(float(best_ocr_score), float(prefix_rescue_score))

        rescued_segment_text, segment_rescue_score = rescue_plate_from_segments(best_text, plate_crop)
        if rescued_segment_text != best_text:
            best_text = rescued_segment_text
            best_ocr_score = max(float(best_ocr_score), float(segment_rescue_score))

        valid_format = 1 if util.license_complies_format(best_text) else 0
        sharpness = plate_sharpness_score(gray)

        full_plate_crop, prefix_crop, middle_crop, suffix_crop = get_plate_segments(plate_crop)

        candidate = {
            "plate_text": best_text,
            "ocr_score": float(best_ocr_score),
            "ocr_support": int(best_support),
            "plate_score": float(plate_score),
            "valid_format": valid_format,
            "sharpness": sharpness,
            "plate_bbox": [float(fx1), float(fy1), float(fx2), float(fy2)],
            "plate_crop": plate_crop,
            "full_plate_crop": full_plate_crop,
            "prefix_crop": prefix_crop,
            "middle_crop": middle_crop,
            "suffix_crop": suffix_crop,
        }

        rank = (
            candidate["valid_format"],
            candidate["ocr_support"],
            candidate["ocr_score"],
            candidate["sharpness"],
            candidate["plate_score"],
        )

        if best is None or rank > (
            best["valid_format"],
            best["ocr_support"],
            best["ocr_score"],
            best["sharpness"],
            best["plate_score"],
        ):
            best = candidate

    return best is not None, best


# =========================================================
# SAVE DEBUG CROPS
# =========================================================
def save_case_crops(base_dir, filename, best):
    if best is None:
        return

    name = os.path.splitext(filename)[0]
    case_dir = os.path.join(base_dir, name)
    os.makedirs(case_dir, exist_ok=True)

    crops = {
        "full_plate_crop": best.get("full_plate_crop"),
        "prefix_crop": best.get("prefix_crop"),
        "middle_crop": best.get("middle_crop"),
        "suffix_crop": best.get("suffix_crop"),
    }

    for crop_name, crop_img in crops.items():
        if crop_img is not None and crop_img.size != 0:
            out_path = os.path.join(case_dir, f"{crop_name}.jpg")
            cv2.imwrite(out_path, crop_img)


def save_case_frame(base_dir, filename, frame, true_plate, pred_plate):
    name = os.path.splitext(filename)[0]
    case_dir = os.path.join(base_dir, name)
    os.makedirs(case_dir, exist_ok=True)

    out_name = f"frame__true_{normalize_plate_key(true_plate)}__pred_{normalize_plate_key(pred_plate)}.jpg"
    out_path = os.path.join(case_dir, out_name)
    cv2.imwrite(out_path, frame)


# =========================================================
# METRICS
# =========================================================
def exact_match(true_plate, pred_plate):
    return int(normalize_plate_key(true_plate) == normalize_plate_key(pred_plate))


def prefix2_match(true_plate, pred_plate):
    t = normalize_plate_key(true_plate)
    p = normalize_plate_key(pred_plate)
    if len(t) < 2 or len(p) < 2:
        return 0
    return int(t[:2] == p[:2])


def middle_match(true_plate, pred_plate):
    t = normalize_plate_key(true_plate)
    p = normalize_plate_key(pred_plate)
    if len(t) < 3 or len(p) < 3:
        return 0
    return int(t[2] == p[2])


def suffix5_match(true_plate, pred_plate):
    t = normalize_plate_key(true_plate)
    p = normalize_plate_key(pred_plate)
    if len(t) < 5 or len(p) < 5:
        return 0
    return int(t[-5:] == p[-5:])


# =========================================================
# EVALUATION
# =========================================================
def evaluate():
    labels = load_labels(LABELS_CSV)

    if not labels:
        raise RuntimeError(f"No labels loaded from: {LABELS_CSV}")

    model_path = PLATE_MODEL_PATHS[MODEL_BACKEND]
    plate_model = YOLO(model_path, task="detect") if MODEL_BACKEND == "engine" else YOLO(model_path)

    if SAVE_BAD_CASE_CROPS:
        os.makedirs(BAD_CASES_DIR, exist_ok=True)

    rows = []
    total = 0
    plate_hits = 0
    exact_hits = 0
    prefix_hits = 0
    middle_hits = 0
    suffix_hits = 0
    valid_hits = 0
    conf_sum = 0.0
    time_sum = 0.0

    for item in labels:
        filename = item["filename"]
        true_plate = item["true_plate"]
        vehicle_type = item["vehicle_type"]
        test_group = item["test_group"]

        img_path = os.path.join(IMAGE_DIR, filename)
        frame = cv2.imread(img_path)

        if frame is None:
            print("FAILED TO READ:", img_path)
            continue

        total += 1

        t0 = time.time()
        plate_detected, best = alpr_on_image(frame, plate_model)
        elapsed = time.time() - t0

        pred_plate = best["plate_text"] if best else ""
        pred_conf = best["ocr_score"] if best else 0.0
        valid_format = int(util.license_complies_format(pred_plate)) if pred_plate else 0

        if plate_detected:
            plate_hits += 1
        if valid_format:
            valid_hits += 1

        ex = exact_match(true_plate, pred_plate)
        p2 = prefix2_match(true_plate, pred_plate)
        mid = middle_match(true_plate, pred_plate)
        suf = suffix5_match(true_plate, pred_plate)

        exact_hits += ex
        prefix_hits += p2
        middle_hits += mid
        suffix_hits += suf

        conf_sum += pred_conf
        time_sum += elapsed

        row = {
            "filename": filename,
            "vehicle_type": vehicle_type,
            "test_group": test_group,
            "true_plate": true_plate,
            "pred_plate": pred_plate,
            "plate_detected": int(plate_detected),
            "valid_format": valid_format,
            "prefix2_match": p2,
            "middle_match": mid,
            "suffix5_match": suf,
            "exact_match": ex,
            "confidence": round(pred_conf, 4),
            "runtime_sec": round(elapsed, 4),
        }
        rows.append(row)

        if SAVE_BAD_CASE_CROPS and ex == 0:
            save_case_frame(BAD_CASES_DIR, filename, frame, true_plate, pred_plate)
            if best is not None:
                save_case_crops(BAD_CASES_DIR, filename, best)

    summary = {
        "model": f"gate_{MODEL_BACKEND}",
        "total_images": total,
        "plate_detect_rate": round(plate_hits / total, 4) if total else 0,
        "valid_format_rate": round(valid_hits / total, 4) if total else 0,
        "prefix2_match_rate": round(prefix_hits / total, 4) if total else 0,
        "middle_match_rate": round(middle_hits / total, 4) if total else 0,
        "suffix5_match_rate": round(suffix_hits / total, 4) if total else 0,
        "ocr_exact_match_rate": round(exact_hits / total, 4) if total else 0,
        "avg_confidence": round(conf_sum / total, 4) if total else 0,
        "avg_runtime_sec": round(time_sum / total, 4) if total else 0,
    }

    if rows:
        with open(DETAILS_OUT, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    with open(SUMMARY_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\nSaved:")
    print(" -", DETAILS_OUT)
    print(" -", SUMMARY_OUT)
    if SAVE_BAD_CASE_CROPS:
        print(" -", BAD_CASES_DIR)


if __name__ == "__main__":
    evaluate()