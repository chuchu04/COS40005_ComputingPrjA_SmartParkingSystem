# SMART PARKING ALPR MODEL - JETSON RUN GUIDE

## Purpose

This guide explains how to run my scaled ALPR model on an NVIDIA Jetson using only the terminal, without Anaconda.

## Important

1. Jetson already comes with the NVIDIA software stack through JetPack, including TensorRT. Do not try to set it up like a Windows desktop GPU environment. ([NVIDIA Docs][1])

2. TensorRT `.engine` files are NOT generally portable across different GPUs, operating systems, or different TensorRT/CUDA/cuDNN stacks. If the `.engine` files were built on my Windows PC, they may fail on Jetson. If that happens, run the `.pt` models first, or rebuild the `.engine` files on the Jetson itself. ([NVIDIA Docs][2])

3. PyTorch on Jetson should be installed using the NVIDIA Jetson-specific wheel that matches the JetPack version on the Jetson. NVIDIA’s Jetson PyTorch guide also recommends installing system prerequisites first, and using a Python virtual environment if you want isolation. ([NVIDIA Docs][3])

## FILES TO COPY TO THE JETSON

Put these files in one folder, for example:

/home/<your_user>/scale_model/

Inside that folder put:

* snapshot_gate.py
* snapshot_gate_engine.py
* util.py
* yolov8n.pt
* license_plate_detector.pt
* yolov8n.engine              (optional, may not work if built on another machine)
* license_plate_detector.engine  (optional, may not work if built on another machine)
* sample2.mp4                 (optional test video)
* sample2z.mp4                (optional test video)

Recommended:

* create an empty folder named captures
* create an empty folder named outputs if needed

## STEP 0 - CHECK JETSON VERSION

Run:

cat /etc/nv_tegra_release

and also:

python3 --version

You need to know the JetPack version before installing the correct PyTorch wheel. The PyTorch wheel must match the JetPack version. Follow the official NVIDIA Jetson PyTorch page for the correct wheel for your JetPack. ([NVIDIA Docs][3])

## STEP 1 - INSTALL BASIC SYSTEM PACKAGES

Run:

sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev libopenblas-dev libjpeg-dev zlib1g-dev libpython3-dev python3-opencv

Why:

* NVIDIA’s Jetson PyTorch guide lists system prerequisites such as `python3-pip` and `libopenblas-dev`. ([NVIDIA Docs][3])
* `python3-opencv` from apt is usually simpler and more reliable on Jetson than trying to force a desktop-style `opencv-python` pip wheel.

## STEP 2 - CREATE A PYTHON ENVIRONMENT

Option A - recommended:

cd /home/<your_user>/scale_model
python3 -m venv jetson_alpr_env
source jetson_alpr_env/bin/activate

If `venv` has issues, use `virtualenv` instead, which NVIDIA also documents for Jetson PyTorch environments. ([NVIDIA Docs][4])

pip install --upgrade pip setuptools wheel

## STEP 3 - INSTALL PYTORCH FOR JETSON

IMPORTANT:
Do NOT just do a random `pip install torch` unless you know it matches Jetson.
Use the NVIDIA Jetson PyTorch install guide and pick the wheel for the exact JetPack version on the Jetson. ([NVIDIA Docs][3])

Example structure from NVIDIA docs:

pip3 install --no-cache <NVIDIA_JETSON_PYTORCH_WHEEL_URL>

After that, verify:

python3 -c "import torch; print(torch.**version**); print(torch.cuda.is_available())"

Expected:

* torch imports successfully
* `torch.cuda.is_available()` should print `True`

## STEP 4 - INSTALL PYTHON PACKAGES FOR THIS PROJECT

After PyTorch is working, run:

pip install ultralytics==8.4.22 easyocr numpy pillow

Notes:

* Do NOT install `onnxruntime-gpu` for this Jetson runtime unless you specifically need it. For this project runtime path, JetPack TensorRT is the important NVIDIA inference stack, not desktop `onnxruntime-gpu`. ([NVIDIA Docs][1])
* If `easyocr` installs extra dependencies, let it finish.
* Since OpenCV was installed from apt, you usually do not need `opencv-python` from pip.

## STEP 5 - TEST BASIC IMPORTS

Run:

python3 -c "import torch, cv2, easyocr, ultralytics; print('imports ok'); print('cuda:', torch.cuda.is_available())"

If this works, your Python environment is okay.

## STEP 6 - TEST THE PT VERSION FIRST

Before trying `.engine`, test the `.pt` version because it is more portable.

Edit `snapshot_gate.py` and check these settings:

* MODE = "entry" or MODE = "exit"
* SOURCE = 0                 for USB camera
  or
* SOURCE = "./sample2.mp4"   for video file test
* SHOW_PREVIEW = False       if the Jetson is being used headless / no monitor GUI

Then run:

python3 snapshot_gate.py

If it works, you should see:

* terminal output with detected plate event
* saved images in captures/
* saved CSV/session output if your script is configured for that

## STEP 7 - TRY THE ENGINE VERSION

Only do this after the PT version works.

Edit `snapshot_gate_engine.py` and check:

* it points to `yolov8n.engine`
* it points to `license_plate_detector.engine`
* MODE is correct
* SOURCE is correct
* SHOW_PREVIEW = False if no GUI

Then run:

python3 snapshot_gate_engine.py

If it works, great.

If it fails to load the `.engine` file, this is likely because the engine was built on another machine and is not compatible with the Jetson environment. TensorRT engines are tied to GPU type and software stack. In that case, rebuild the engine on the Jetson or stay with the `.pt` version for now. ([NVIDIA Docs][2])

## STEP 8 - IF ENGINE FILES FAIL, USE PT FIRST

If you get errors loading:

* yolov8n.engine
* license_plate_detector.engine

do this:

1. keep using:

   * yolov8n.pt
   * license_plate_detector.pt
2. confirm the whole pipeline works on Jetson
3. rebuild TensorRT engines later on the Jetson itself

This is the safest order.

## HOW TO REBUILD ENGINE ON THE JETSON LATER

Only do this if:

* the PT version works
* the Jetson environment has working PyTorch + Ultralytics + TensorRT access

Then rebuild `.engine` on the Jetson from the `.pt` models, so the engines match:

* Jetson GPU
* JetPack
* TensorRT version
* CUDA/cuDNN stack

Reason:
TensorRT engine portability is limited. NVIDIA explicitly warns not to build in one environment and run in another different GPU/software environment. ([NVIDIA Docs][2])

## RECOMMENDED PROJECT FOLDER

Example:

/home/<your_user>/scale_model/
├── jetson_alpr_env/
├── captures/
├── snapshot_gate.py
├── snapshot_gate_engine.py
├── util.py
├── yolov8n.pt
├── license_plate_detector.pt
├── yolov8n.engine
├── license_plate_detector.engine
├── sample2.mp4
└── sample2z.mp4

## WHICH FILE SHOULD MY TEAMMATE RUN?

For first-time setup:

* run `snapshot_gate.py` first

After PT version works:

* try `snapshot_gate_engine.py`

Why:

* PT version is easier to debug
* engine version is faster, but more fragile if the engine file was built on another machine

## RECOMMENDED REQUIREMENTS FOR JETSON

Use this as the Jetson-side package list after PyTorch is installed correctly from NVIDIA’s guide:

ultralytics==8.4.22
easyocr
numpy
pillow

Do not copy the desktop `requirements.txt` blindly.
For Jetson runtime:

* OpenCV is better installed with `apt`
* PyTorch should come from NVIDIA Jetson wheels
* `onnxruntime-gpu` is not needed for this runtime path

## QUICK TROUBLESHOOTING

1. Error: No module named torch

* PyTorch is not installed correctly for Jetson
* install the correct NVIDIA Jetson wheel matching JetPack ([NVIDIA Docs][3])

2. Error: No module named cv2

* run:
  sudo apt install -y python3-opencv

3. Error: No module named easyocr

* run:
  pip install easyocr

4. Error: engine file cannot load / TensorRT failure

* use `.pt` first
* rebuild `.engine` on Jetson later
* engine files may not be portable from my Windows PC build ([NVIDIA Docs][2])

5. Error: GUI / cv2.imshow problems

* set:
  SHOW_PREVIEW = False

6. Error: camera cannot open

* check USB camera
* check `SOURCE = 0`
* test camera separately with a simple OpenCV script

7. PT runs but is slow

* that is okay for first validation
* only optimize to TensorRT after PT pipeline is confirmed working

## MINIMUM RUN ORDER FOR MY TEAMMATE

1. Check JetPack version
2. Install system packages
3. Create Python venv
4. Install NVIDIA Jetson PyTorch wheel
5. Install ultralytics, easyocr, numpy, pillow
6. Run `snapshot_gate.py` with a sample video
7. If PT works, then try `snapshot_gate_engine.py`
8. If engine fails, continue using PT and rebuild engines later on Jetson

## FINAL NOTE

The most common reason for failure on Jetson is:

* trying to use a TensorRT engine built on a different machine

So the safest rule is:

* PT first
* engine second
* rebuild engine on Jetson if needed

---

If you want, I can also paste a second file for you:
`requirements_jetson.txt`
in plain text so your teammate can use it directly.

[1]: https://docs.nvidia.com/deeplearning/tensorrt/archives/tensorrt-1001/pdf/TensorRT-Installation-Guide.pdf?utm_source=chatgpt.com "NVIDIA TensorRT - Installation Guide"
[2]: https://docs.nvidia.com/deeplearning/tensorrt/latest/reference/troubleshooting.html?utm_source=chatgpt.com "Troubleshooting — NVIDIA TensorRT"
[3]: https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html?utm_source=chatgpt.com "Installing PyTorch for Jetson Platform - NVIDIA Docs"
[4]: https://docs.nvidia.com/deeplearning/frameworks/pdf/Install-PyTorch-Jetson-Platform.pdf?utm_source=chatgpt.com "Installing PyTorch For Jetson Platform"
