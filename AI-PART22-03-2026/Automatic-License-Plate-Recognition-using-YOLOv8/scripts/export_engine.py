from ultralytics import YOLO

# Vehicle detector
vehicle_model = YOLO("yolov8n.pt")
vehicle_model.export(
    format="engine",
    imgsz=640,
    batch=1,
    half=True,
    dynamic=False,
    simplify=True,
    workspace=4,   # GiB
    device=0
)

# Plate detector
plate_model = YOLO("license_plate_detector.pt")
plate_model.export(
    format="engine",
    imgsz=640,
    batch=1,
    half=True,
    dynamic=False,
    simplify=True,
    workspace=4,
    device=0
)