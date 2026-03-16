import string
import easyocr

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


def normalize_plate_text(text):
    return ''.join(ch for ch in text.upper() if ch.isalnum())


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


def generate_vn_candidates(text):
    """
    Generate plausible VN plate candidates from OCR text.
    Priority:
    - normal private car pattern: 2 digits + 1 letter + 5 digits (len 8)
    - fallback: 2 digits + 2 letters + 5 digits (len 9)
    """
    text = normalize_plate_text(text)
    candidates = []

    if len(text) == 8:
        cand = try_pattern(text, [2])   # preferred normal car format
        if cand:
            candidates.append(cand)

    elif len(text) == 9:
        # try one-letter and two-letter interpretations
        cand1 = try_pattern(text, [2])
        cand2 = try_pattern(text, [2, 3])
        if cand1:
            candidates.append(cand1)
        if cand2 and cand2 not in candidates:
            candidates.append(cand2)

    elif len(text) == 7:
        # allow a loose fallback, but do not force-format too aggressively
        cand = try_pattern(text, [2])
        if cand:
            candidates.append(cand)

    return candidates


def format_vn_plate(text):
    """
    Format corrected VN plate string.
    Examples:
    51A72702  -> 51A-727.02
    30AB12345 -> 30AB-123.45
    """
    if text is None:
        return None

    if len(text) == 8:
        return f"{text[:3]}-{text[3:6]}.{text[6:]}"
    elif len(text) == 9 and text[2:4].isalpha():
        return f"{text[:4]}-{text[4:7]}.{text[7:]}"
    else:
        return text


def license_complies_format(text):
    return len(generate_vn_candidates(text)) > 0


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