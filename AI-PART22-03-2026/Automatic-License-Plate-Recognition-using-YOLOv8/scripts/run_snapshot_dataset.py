import os
import csv
import cv2
import json
import snapshot_gate as sg

IMAGE_DIR = r"C:\Users\PC\Automatic-License-Plate-Recognition-using-YOLOv8\test_eval\images"
LABELS_CSV = os.path.join(IMAGE_DIR, "labels.csv")

OUTPUT_CSV = "snapshot_dataset_results.csv"
SAVE_CROPS = True
SAVE_DIR = "snapshot_dataset_outputs"

os.makedirs(SAVE_DIR, exist_ok=True)


def load_labels(path):
    labels = {}
    if not os.path.exists(path):
        return labels

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            true_plate = row.get("true_plate", "").strip().upper()
            if filename:
                labels[filename] = true_plate
    return labels


def normalize_plate(text):
    if text is None:
        return ""
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def save_case_outputs(filename, frame, result):
    name = os.path.splitext(filename)[0]
    case_dir = os.path.join(SAVE_DIR, name)
    os.makedirs(case_dir, exist_ok=True)

    cv2.imwrite(os.path.join(case_dir, "frame.jpg"), frame)

    if result is not None and result.get("plate_crop") is not None:
        cv2.imwrite(os.path.join(case_dir, "plate_crop.jpg"), result["plate_crop"])


def main():
    labels = load_labels(LABELS_CSV)

    rows = []

    image_files = [
        f for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp"))
    ]
    image_files.sort()

    for filename in image_files:
        img_path = os.path.join(IMAGE_DIR, filename)
        frame = cv2.imread(img_path)

        if frame is None:
            print("FAILED TO READ:", img_path)
            continue

        result = sg.alpr_on_frame(frame)

        true_plate = labels.get(filename, "")
        pred_plate = result["plate_text"] if result else ""
        conf = float(result["ocr_score"]) if result else 0.0
        valid_format = int(sg.util.license_complies_format(pred_plate)) if pred_plate else 0

        exact_match = int(
            normalize_plate(true_plate) == normalize_plate(pred_plate)
        ) if true_plate else 0

        row = {
            "filename": filename,
            "true_plate": true_plate,
            "pred_plate": pred_plate,
            "valid_format": valid_format,
            "exact_match": exact_match,
            "confidence": round(conf, 4),
            "plate_bbox": json.dumps(result["plate_bbox"]) if result else "",
        }
        rows.append(row)

        print(f"{filename} -> {pred_plate} | conf={conf:.4f}")

        if SAVE_CROPS:
            save_case_outputs(filename, frame, result)

    if rows:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print("\nSaved:", OUTPUT_CSV)
    if SAVE_CROPS:
        print("Saved crops/frames to:", SAVE_DIR)


if __name__ == "__main__":
    main()