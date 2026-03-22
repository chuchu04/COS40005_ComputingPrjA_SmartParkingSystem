import ast

import cv2
import numpy as np
import pandas as pd


def draw_border(img, top_left, bottom_right, color=(0, 255, 0), thickness=10, line_length_x=200, line_length_y=200):
    x1, y1 = top_left
    x2, y2 = bottom_right

    cv2.line(img, (x1, y1), (x1, y1 + line_length_y), color, thickness)  #-- top-left
    cv2.line(img, (x1, y1), (x1 + line_length_x, y1), color, thickness)

    cv2.line(img, (x1, y2), (x1, y2 - line_length_y), color, thickness)  #-- bottom-left
    cv2.line(img, (x1, y2), (x1 + line_length_x, y2), color, thickness)

    cv2.line(img, (x2, y1), (x2 - line_length_x, y1), color, thickness)  #-- top-right
    cv2.line(img, (x2, y1), (x2, y1 + line_length_y), color, thickness)

    cv2.line(img, (x2, y2), (x2, y2 - line_length_y), color, thickness)  #-- bottom-right
    cv2.line(img, (x2, y2), (x2 - line_length_x, y2), color, thickness)

    return img


results = pd.read_csv('./test_interpolated.csv')
raw = pd.read_csv('./test.csv')

# Make sure license_number is handled as string when needed
# --- build final plate text per car_id using voting + score tie-break ---
raw['license_number_str'] = raw['license_number'].astype(str)

# keep only OCR rows that are not 0
raw_ok = raw[(raw['license_number_str'] != '0') & (raw['license_number_score'] > 0)].copy()

def normalize_plate_key(text):
    return ''.join(ch for ch in str(text).upper() if ch.isalnum())

def pattern_bonus(key):
    # prefer normal VN car plate structure
    # 2 digits + 1 letter + 5 digits  -> len 8
    # 2 digits + 2 letters + 5 digits -> len 9
    if len(key) == 8 and key[:2].isdigit() and key[2].isalpha() and key[3:].isdigit():
        return 2
    if len(key) == 9 and key[:2].isdigit() and key[2:4].isalpha() and key[4:].isdigit():
        return 1
    return 0

raw_ok['plate_key'] = raw_ok['license_number_str'].apply(normalize_plate_key)

best_text = {}
best_key = {}
best_source_row = {}

for car_id in sorted(raw_ok['car_id'].unique()):
    car_rows = raw_ok[raw_ok['car_id'] == car_id].copy()
    if len(car_rows) == 0:
        continue

    grouped = car_rows.groupby('plate_key').agg(
        count=('plate_key', 'count'),
        max_score=('license_number_score', 'max'),
        mean_score=('license_number_score', 'mean')
    ).reset_index()

    grouped['bonus'] = grouped['plate_key'].apply(pattern_bonus)

    # choose winner by:
    # 1. better VN pattern
    # 2. higher frequency
    # 3. higher max OCR score
    # 4. higher mean OCR score
    grouped = grouped.sort_values(
        by=['bonus', 'count', 'max_score', 'mean_score'],
        ascending=[False, False, False, False]
    )

    winner_key = grouped.iloc[0]['plate_key']
    winner_rows = car_rows[car_rows['plate_key'] == winner_key].copy()
    winner_rows = winner_rows.sort_values(by='license_number_score', ascending=False)

    best_key[int(car_id)] = winner_key
    best_text[int(car_id)] = str(winner_rows.iloc[0]['license_number_str'])
    best_source_row[int(car_id)] = winner_rows.iloc[0]

# load video
video_path = 'sample2.mp4'
cap = cv2.VideoCapture(video_path)

fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Specify the codec
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter('./out.mp4', fourcc, fps, (width, height))

license_plate = {}

for car_id in np.unique(results['car_id']):
    car_id = int(car_id)

    license_plate[car_id] = {
        'license_crop': None,
        'license_plate_number': best_text.get(car_id, 'Unknown')
    }

    # use the best raw OCR row as the source for crop extraction
    if car_id in best_source_row:
        source_row = best_source_row[car_id]
        source_frame = int(source_row['frame_nmr'])
        source_bbox = source_row['license_plate_bbox']
    else:
        # fallback if this car never had valid OCR
        fallback_rows = results[results['car_id'] == car_id]
        if len(fallback_rows) == 0:
            continue
        fallback_row = fallback_rows.sort_values(by='license_plate_bbox_score', ascending=False).iloc[0]
        source_frame = int(fallback_row['frame_nmr'])
        source_bbox = fallback_row['license_plate_bbox']

    cap.set(cv2.CAP_PROP_POS_FRAMES, source_frame)
    ret, frame = cap.read()
    if not ret or frame is None:
        continue

    x1, y1, x2, y2 = ast.literal_eval(
        str(source_bbox).replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ',')
    )
    

    h, w = frame.shape[:2]

    x1 = max(0, min(int(x1), w - 1))
    x2 = max(0, min(int(x2), w - 1))
    y1 = max(0, min(int(y1), h - 1))
    y2 = max(0, min(int(y2), h - 1))

    if x2 <= x1 or y2 <= y1:
        license_plate[car_id]['license_crop'] = None
        continue

    license_crop = frame[y1:y2, x1:x2, :]
    
    if license_crop.size == 0 or (int(y2) - int(y1)) <= 0 or (int(x2) - int(x1)) <= 0:
        continue

    den = max(1, (y2 - y1))
    new_w = int((x2 - x1) * 400 / den)
    if new_w <= 0:
        license_plate[car_id]['license_crop'] = None
        continue

    license_crop = cv2.resize(license_crop, (new_w, 400))
    license_plate[car_id]['license_crop'] = license_crop



frame_nmr = -1

cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

# read frames
ret = True
while ret:
    ret, frame = cap.read()
    frame_nmr += 1
    if ret:
        df_ = results[results['frame_nmr'] == frame_nmr]
        for row_indx in range(len(df_)):
            # draw car
            car_x1, car_y1, car_x2, car_y2 = ast.literal_eval(df_.iloc[row_indx]['car_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ','))
            draw_border(frame, (int(car_x1), int(car_y1)), (int(car_x2), int(car_y2)), (0, 255, 0), 25,
                        line_length_x=200, line_length_y=200)

            # draw license plate
            x1, y1, x2, y2 = ast.literal_eval(df_.iloc[row_indx]['license_plate_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ','))
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 12)

            car_id = int(df_.iloc[row_indx]['car_id'])
            plate_text = best_text.get(car_id, None)

            label = plate_text if plate_text is not None else "Unknown"
            cv2.putText(frame, label, (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)


            # crop license plate
            car_id = int(df_.iloc[row_indx]['car_id'])
            license_crop = license_plate.get(car_id, {}).get('license_crop', None)
            if license_crop is None:
                continue

            H, W, _ = license_crop.shape

            try:
                frame[int(car_y1) - H - 100:int(car_y1) - 100,
                      int((car_x2 + car_x1 - W) / 2):int((car_x2 + car_x1 + W) / 2), :] = license_crop

                frame[int(car_y1) - H - 400:int(car_y1) - H - 100,
                      int((car_x2 + car_x1 - W) / 2):int((car_x2 + car_x1 + W) / 2), :] = (255, 255, 255)

                (text_width, text_height), _ = cv2.getTextSize(
                    license_plate[car_id]['license_plate_number'],
                    cv2.FONT_HERSHEY_SIMPLEX,
                    4.3,
                    17)

                cv2.putText(frame,
                            license_plate[car_id]['license_plate_number'],
                            (int((car_x2 + car_x1 - text_width) / 2), int(car_y1 - H - 250 + (text_height / 2))),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            4.3,
                            (0, 0, 0),
                            17)

            except:
                pass

        out.write(frame)
        frame = cv2.resize(frame, (1280, 720))

        # cv2.imshow('frame', frame)
        # cv2.waitKey(0)

out.release()
cap.release()
