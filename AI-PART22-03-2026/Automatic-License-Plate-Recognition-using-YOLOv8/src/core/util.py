import string
import easyocr
import string
import cv2
import easyocr
import re

# Initialize the OCR reader
reader = easyocr.Reader(['en'], gpu=True)

# # Mapping dictionaries for character conversion
# dict_char_to_int = {
#     'O': '0',
#     'I': '1',
#     'J': '3',
#     'A': '4',
#     'G': '6',
#     'S': '5'
# }

# dict_int_to_char = {
#     '0': 'O',
#     '1': 'I',
#     '3': 'J',
#     '4': 'A',
#     '6': 'G',
#     '5': 'S'
# }


def write_csv(results, output_path):
    with open(output_path, 'w') as f:
        f.write('{},{},{},{},{},{},{}\n'.format(
            'frame_nmr', 'car_id', 'car_bbox',
            'license_plate_bbox', 'license_plate_bbox_score',
            'license_number', 'license_number_score'
        ))

        for frame_nmr in results.keys():
            for car_id in results[frame_nmr].keys():
                if 'car' in results[frame_nmr][car_id].keys() and \
                   'license_plate' in results[frame_nmr][car_id].keys() and \
                   'text' in results[frame_nmr][car_id]['license_plate'].keys():
                    f.write('{},{},{},{},{},{},{}\n'.format(
                        frame_nmr,
                        car_id,
                        '[{} {} {} {}]'.format(
                            results[frame_nmr][car_id]['car']['bbox'][0],
                            results[frame_nmr][car_id]['car']['bbox'][1],
                            results[frame_nmr][car_id]['car']['bbox'][2],
                            results[frame_nmr][car_id]['car']['bbox'][3]
                        ),
                        '[{} {} {} {}]'.format(
                            results[frame_nmr][car_id]['license_plate']['bbox'][0],
                            results[frame_nmr][car_id]['license_plate']['bbox'][1],
                            results[frame_nmr][car_id]['license_plate']['bbox'][2],
                            results[frame_nmr][car_id]['license_plate']['bbox'][3]
                        ),
                        results[frame_nmr][car_id]['license_plate']['bbox_score'],
                        results[frame_nmr][car_id]['license_plate']['text'],
                        results[frame_nmr][car_id]['license_plate']['text_score']
                    ))


# def normalize_plate_text(text):
#     return ''.join(ch for ch in text.upper() if ch.isalnum())

def normalize_plate_text(text):
    if text is None:
        return ""
    return ''.join(ch for ch in str(text).upper() if ch.isalnum())

# Safer mappings: only use the most common OCR confusions
LETTER_TO_DIGIT = {
    'O': '0',
    'Q': '0',
    'D': '0',
    'I': '1',
    'L': '1',
    'Z': '2',
    'S': '5',
    'B': '8'
}

DIGIT_TO_LETTER = {
    # '0': 'O',
    # '1': 'I',
    '4': 'A',
    # '5': 'S',
    '8': 'B'
}


def try_pattern(text, letter_positions):
    """
    Try to convert text into a VN-like plate candidate using position rules.
    Returns corrected candidate or None.
    """
    chars = list(text)
    n = len(chars)

    # first 2 positions should be digits
    for i in [0, 1]:
        if i >= n:
            return None
        if chars[i].isalpha():
            chars[i] = LETTER_TO_DIGIT.get(chars[i], chars[i])

    # specified letter positions
    for i in letter_positions:
        if i >= n:
            return None
        if chars[i].isdigit():
            chars[i] = DIGIT_TO_LETTER.get(chars[i], chars[i])

    # all other positions after the letters should be digits
    digit_positions = [i for i in range(2, n) if i not in letter_positions]
    for i in digit_positions:
        if chars[i].isalpha():
            chars[i] = LETTER_TO_DIGIT.get(chars[i], chars[i])

    candidate = ''.join(chars)

    # validate
    if not candidate[:2].isdigit():
        return None

    for i in letter_positions:
        if i >= len(candidate) or not candidate[i].isalpha():
            return None

    for i in range(2, len(candidate)):
        if i not in letter_positions and not candidate[i].isdigit():
            return None

    return candidate


# def generate_vn_candidates(text):
#     """
#     Generate plausible VN plate candidates from OCR text.
#     Priority:
#     - normal private car pattern: 2 digits + 1 letter + 5 digits (len 8)
#     - fallback: 2 digits + 2 letters + 5 digits (len 9)
#     """
#     text = normalize_plate_text(text)
#     candidates = []

#     if len(text) == 8:
#         cand = try_pattern(text, [2])   # preferred normal car format
#         if cand:
#             candidates.append(cand)

#     elif len(text) == 9:
#         # try one-letter and two-letter interpretations
#         cand1 = try_pattern(text, [2])
#         cand2 = try_pattern(text, [2, 3])
#         if cand1:
#             candidates.append(cand1)
#         if cand2 and cand2 not in candidates:
#             candidates.append(cand2)

#     elif len(text) == 7:
#         # allow a loose fallback, but do not force-format too aggressively
#         cand = try_pattern(text, [2])
#         if cand:
#             candidates.append(cand)

#     return candidates

def generate_vn_candidates(text):
    """
    Strict candidate generator for current live demo domain:
    Only accept VN one-line plate pattern:
        2 digits + 1 letter + 5 digits
    Example:
        51F57493 -> valid
        61A22959 -> valid
        30F86034 -> valid

    Do NOT accept:
        - len 7
        - len 9
        - 2-letter formats
        - loose fallback patterns
    """
    text = normalize_plate_text(text)
    candidates = []

    if len(text) != 8:
        return candidates

    cand = try_pattern(text, [2])   # only one-letter pattern
    if cand:
        candidates.append(cand)

    return candidates

# def format_vn_plate(text):
#     """
#     Format corrected VN plate string.
#     Examples:
#     51A72702  -> 51A-727.02
#     30AB12345 -> 30AB-123.45
#     """
#     if text is None:
#         return None

#     if len(text) == 8:
#         return f"{text[:3]}-{text[3:6]}.{text[6:]}"
#     elif len(text) == 9 and text[2:4].isalpha():
#         return f"{text[:4]}-{text[4:7]}.{text[7:]}"
#     else:
#         return text

def format_vn_plate(text):
    """
    Format strict VN one-line plate:
    51F57493 -> 51F-574.93
    """
    if text is None:
        return None

    text = normalize_plate_text(text)
    if len(text) == 8 and text[:2].isdigit() and text[2].isalpha() and text[3:].isdigit():
        return f"{text[:3]}-{text[3:6]}.{text[6:]}"
    return text


# def license_complies_format(text):
#     return len(generate_vn_candidates(text)) > 0

def license_complies_format(text):
    """
    Strict validator for current live demo:
    Accept only:
      - raw:       NNLNNNNN
      - formatted: NNL-NNN.NN
    """
    if text is None:
        return False

    raw = normalize_plate_text(text)

    # raw strict form
    if len(raw) == 8 and raw[:2].isdigit() and raw[2].isalpha() and raw[3:].isdigit():
        return True

    # formatted strict form
    text = str(text).upper().strip()
    if re.fullmatch(r"\d{2}[A-Z]-\d{3}\.\d{2}", text):
        return True

    return False

def read_license_plate(license_plate_crop):
    detections = reader.readtext(license_plate_crop)

    best_text = None
    best_score = 0.0

    best_fallback = None
    best_fallback_score = 0.0

    for bbox, text, score in detections:
        cleaned = normalize_plate_text(text)
        candidates = generate_vn_candidates(cleaned)

        # Prefer corrected VN-valid candidates
        if candidates:
            for cand in candidates:
                candidate_score = score

                # prefer the common private-car pattern: 2 digits + 1 letter + 5 digits
                if len(cand) == 8 and cand[2].isalpha():
                    candidate_score += 0.12

                if candidate_score > best_score:
                    best_text = format_vn_plate(cand)
                    best_score = candidate_score

        # Keep a softer fallback instead of turning everything into 0
        # only if OCR looks somewhat plausible
        if 7 <= len(cleaned) <= 9 and score > best_fallback_score:
            best_fallback = cleaned
            best_fallback_score = score

    if best_text is not None:
        return best_text, best_score

    # fallback: keep plausible raw OCR if it is reasonably confident
    if best_fallback is not None and best_fallback_score >= 0.35:
        return best_fallback, best_fallback_score

    return None, None

def get_car(license_plate, vehicle_track_ids):
    x1, y1, x2, y2, score, class_id = license_plate

    foundIt = False
    for j in range(len(vehicle_track_ids)):
        xcar1, ycar1, xcar2, ycar2, car_id = vehicle_track_ids[j]

        if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
            car_indx = j
            foundIt = True
            break

    if foundIt:
        return vehicle_track_ids[car_indx]

    return -1, -1, -1, -1, -1

def choose_segment_candidate(candidates):
    """
    candidates: list of (text, score)
    Vote theo:
    - số lần xuất hiện
    - max score
    - mean score
    """
    if not candidates:
        return None, 0.0

    grouped = {}

    for text, score in candidates:
        key = str(text).strip().upper()
        if not key:
            continue

        if key not in grouped:
            grouped[key] = {
                "count": 0,
                "max_score": 0.0,
                "score_sum": 0.0,
            }

        grouped[key]["count"] += 1
        grouped[key]["max_score"] = max(grouped[key]["max_score"], float(score))
        grouped[key]["score_sum"] += float(score)

    if not grouped:
        return None, 0.0

    for key in grouped:
        grouped[key]["mean_score"] = grouped[key]["score_sum"] / grouped[key]["count"]

    ranked = sorted(
        grouped.items(),
        key=lambda item: (
            item[1]["count"],
            item[1]["max_score"],
            item[1]["mean_score"],
        ),
        reverse=True
    )

    best_key, best_info = ranked[0]
    return best_key, best_info["max_score"]

def read_prefix_digits(image):
    """
    OCR riêng cho 2 số đầu của biển ô tô 1 dòng VN.
    Chỉ cho phép 0-9.
    Dùng nhiều biến thể preprocess + voting.
    Return: (best_digits, best_score)
    """
    if image is None or image.size == 0:
        return None, 0.0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # resize lớn hơn để OCR rõ nét
    gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)

    # tăng contrast
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # sharpen nhẹ
    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)

    # threshold variants
    _, otsu = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, otsu_inv = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    adaptive = cv2.adaptiveThreshold(
        sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21,
        7
    )

    # morphology để làm nét số rõ hơn
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)

    variants = [gray, sharp, otsu, otsu_inv, adaptive, closed]

    raw_candidates = []

    for variant in variants:
        try:
            results = reader.readtext(
                variant,
                detail=1,
                paragraph=False,
                allowlist="0123456789"
            )
        except Exception:
            results = []

        for result in results:
            if len(result) < 3:
                continue

            text = str(result[1]).strip()
            score = float(result[2])

            text = "".join(ch for ch in text if ch.isdigit())

            if len(text) >= 2:
                # ưu tiên lấy 2 số đầu
                raw_candidates.append((text[:2], score))

    best_digits, best_score = choose_segment_candidate(raw_candidates)

    if best_digits is None:
        return None, 0.0

    if len(best_digits) != 2:
        return None, 0.0

    return best_digits, float(best_score)

def read_middle_letter(image):
    """
    OCR riêng cho ký tự chữ ở vị trí thứ 3 của biển ô tô 1 dòng VN.
    Dùng nhiều biến thể preprocess + voting.
    Quan trọng:
    - bỏ I, O, Q, J, W khỏi allowlist để giảm nhầm
    - thêm G vào allowlist (trước đó thiếu G)
    Return: (best_char, best_score)
    """
    if image is None or image.size == 0:
        return None, 0.0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)

    _, otsu = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, otsu_inv = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    adaptive = cv2.adaptiveThreshold(
        sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21,
        7
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)

    variants = [gray, sharp, otsu, otsu_inv, adaptive, closed]

    raw_candidates = []

    # BỎ I để tránh bias sang I
    # THÊM G để case 51G-... có thể đọc đúng
    letter_allowlist = "ABCDEFGHKLMNPRSTUVXYZ"

    for variant in variants:
        try:
            results = reader.readtext(
                variant,
                detail=1,
                paragraph=False,
                allowlist=letter_allowlist
            )
        except Exception:
            results = []

        for result in results:
            if len(result) < 3:
                continue

            text = str(result[1]).upper().strip()
            score = float(result[2])

            text = "".join(ch for ch in text if ch.isalpha())
            if not text:
                continue

            # chỉ lấy ký tự đầu tiên
            raw_candidates.append((text[0], score))

    best_char, best_score = choose_segment_candidate(raw_candidates)

    if best_char is None:
        return None, 0.0

    if len(best_char) != 1:
        return None, 0.0

    return best_char, float(best_score)




def read_suffix_digits(image):
    """
    OCR riêng cho 5 số cuối của biển ô tô 1 dòng VN.
    Chỉ cho phép đọc số 0-9.
    Return: (best_digits, best_score)
    """
    if image is None or image.size == 0:
        return None, 0.0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    gray = cv2.resize(gray, None, fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)

    _, otsu = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, otsu_inv = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    variants = [gray, sharp, otsu, otsu_inv]

    best_digits = None
    best_score = 0.0

    for variant in variants:
        try:
            results = reader.readtext(
                variant,
                detail=1,
                paragraph=False,
                allowlist="0123456789"
            )
        except Exception:
            results = []

        for result in results:
            if len(result) < 3:
                continue

            text = str(result[1]).strip()
            score = float(result[2])

            text = "".join(ch for ch in text if ch.isdigit())

            # cần đủ 5 số cuối
            if len(text) >= 5:
                digits = text[:5]
                if score > best_score:
                    best_digits = digits
                    best_score = score

    return best_digits, best_score