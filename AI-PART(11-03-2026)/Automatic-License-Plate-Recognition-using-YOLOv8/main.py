from ultralytics import YOLO
import cv2
import numpy as np
import util
from sort.sort import *
from util import get_car, read_license_plate, write_csv


results = {}

mot_tracker = Sort()

# load models
coco_model = YOLO('yolov8n.pt')
license_plate_detector = YOLO('license_plate_detector.pt')

# load video
cap = cv2.VideoCapture('./sample2.mp4')

vehicles = [2, 3, 5, 7]

# read frames
frame_nmr = -1
ret = True
while ret:
    frame_nmr += 1
    ret, frame = cap.read()
    if ret:
        results[frame_nmr] = {}
        # detect vehicles
        detections = coco_model(frame)[0]
        detections_ = []
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])

        # track vehicles
        dets = np.asarray(detections_, dtype=float)

        # SORT expects (N, 5). If no detections, pass an empty (0, 5) array.
        if dets.size == 0:
            dets = np.empty((0, 5), dtype=float)
        else:
            dets = dets.reshape(-1, 5)

        track_ids = mot_tracker.update(dets)


        # detect license plates
        license_plates = license_plate_detector(frame)[0]
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate

            # assign license plate to car
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

            if car_id != -1:

                # crop license plate with padding + boundary clipping
                h, w = frame.shape[:2]
                
                pad_x = int((x2 - x1) * 0.10)   # 10% horizontal padding
                pad_y = int((y2 - y1) * 0.18)   # 18% vertical padding
                
                cx1 = max(0, int(x1) - pad_x)
                cy1 = max(0, int(y1) - pad_y)
                cx2 = min(w, int(x2) + pad_x)
                cy2 = min(h, int(y2) + pad_y)
                
                if cx2 <= cx1 or cy2 <= cy1:
                    continue
                
                license_plate_crop = frame[cy1:cy2, cx1:cx2, :]
                if license_plate_crop.size == 0:
                    continue
                
                # upscale crop before OCR
                scale = 2.5
                license_plate_crop = cv2.resize(
                    license_plate_crop,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC
                )
                
                # grayscale
                license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                
                # contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                license_plate_crop_gray = clahe.apply(license_plate_crop_gray)
                
                # denoise but keep edges
                license_plate_crop_gray = cv2.bilateralFilter(license_plate_crop_gray, 7, 50, 50)
                
                # two OCR variants: enhanced grayscale + adaptive threshold
                license_plate_crop_thresh = cv2.adaptiveThreshold(
                    license_plate_crop_gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31,
                    11
                )

# try OCR on both versions and keep the better one
                # try OCR on both versions and keep the better one
                text_gray, score_gray = read_license_plate(license_plate_crop_gray)
                text_thresh, score_thresh = read_license_plate(license_plate_crop_thresh)

                score_gray = 0.0 if score_gray is None else score_gray
                score_thresh = 0.0 if score_thresh is None else score_thresh

                if score_thresh >= score_gray:
                    license_plate_text, license_plate_text_score = text_thresh, score_thresh
                else:
                    license_plate_text, license_plate_text_score = text_gray, score_gray
                # # crop license plate
                # license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]
                # if license_plate_crop.size == 0:
                #     continue
                # # process license plate
                # license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                # _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)

                # # read license plate number
                # license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)

                # Always log the detection; if OCR fails, mark as unknown
                if license_plate_text is None:
                    license_plate_text = '0'
                    license_plate_text_score = 0.0

                results[frame_nmr][car_id] = {
                    'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                    'license_plate': {
                        'bbox': [x1, y1, x2, y2],
                        'text': license_plate_text,
                        'bbox_score': score,
                        'text_score': license_plate_text_score
                    }
                }



# write results
write_csv(results, './test.csv')