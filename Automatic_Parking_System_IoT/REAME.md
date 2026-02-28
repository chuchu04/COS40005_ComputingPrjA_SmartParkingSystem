# 🚗 Smart Parking Gate System (ESP32-S3)

An **ESP32-S3–based smart parking gate prototype** that manages vehicle entrance, parking slot availability, and gate control using **IR sensors, a servo motor, and dual displays (LCD + OLED)**.

This project focuses **only on the IoT / edge-device layer**.  
AI inference, image processing, and database operations are **handled externally** (e.g., by a Raspberry Pi 5 in later phases).

---

## 📌 Demo

🎥 Recommended: watch on a laptop/desktop, 720p for best clarity

```code
https://liveswinburneeduau-my.sharepoint.com/:v:/g/personal/104663478_student_swin_edu_au/IQDfPWRABZLpRLktFPnx2xjGARYKEp7BMAqSHZeYZpvDJNQ?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=gSuQU6
```

---

## 📌 Features

- 🚘 **Entrance car detection** using IR sensor (triggers AI license plate scanning externally)
- 🅿️ **Parking slot availability tracking**  
  *(currently single-slot implementation)*
- 🔐 **Servo-controlled gate with safety logic**
  - Gate opens when a car is detected and a slot is available
  - Gate **will not close** while a vehicle is still detected by the IR sensor
  - Gate **closes automatically after a configurable timeout** once the vehicle has passed
- 📟 **16×2 I2C LCD** for parking slot availability
- 🖥️ **0.96" OLED (SSD1306)** for entrance notifications
- ⏱️ **Non-blocking logic**
  - All timing (gate auto-close and display updates) is handled using `millis()` instead of `delay()`, ensuring continuous sensor monitoring and safe real-time control.
- 🧪 **Serial debug logs** for testing and validation

---

## 🧠 System Behavior Overview

### 🚪 Entrance Flow

Car detected by **Entrance IR sensor**  
⬇️  
OLED displays: `🚗 Car detected`  
⬇️  

**If parking is full**
- OLED displays: `❌ Parking FULL`
- Gate remains **closed**

**If parking is available**
- OLED displays: `🔓 Gate opening`
- Servo opens the gate
- Gate stays open while the car is in IR range
- After the car exits the IR sensor range → a timeout countdown begins, then the gate closes automatically

---

### 🅿️ Slot Monitoring
- Slot IR sensor updates availability in real time
- LCD displays:

Slot available:
0 / 1


---

## 🔌 Hardware Requirements
- ESP32-S3
- IR Sensors ×2  
  - Entrance detection  
  - Slot occupancy detection
- Servo motor (SG90 / MG90S)
- 16×2 I2C LCD (Address: `0x27`)
- 0.96" SSD1306 OLED (128×64, Address: `0x3C`)
- External **5V power supply** (e.g. WH-131)
- **Common GND** across all components
(connected to the WH-131's GND rail)


⚠️ **Important:**  
```text
Servo **VCC must be 5V**, not 3.3V (3.3v would be insufficient and cause jittering in servo).
```

---

## 🔧 Pin Configuration

| Component      | ESP32-S3 GPIO |
|----------------|---------------|
| Entrance IR    | GPIO 6        |
| Slot IR        | GPIO 7        |
| Servo Signal   | GPIO 5        |
| I2C SDA        | GPIO 8        |
| I2C SCL        | GPIO 9        |

> OLED and LCD share the same I2C bus (SDA/SCL).

---

## ⚙️ Configuration Constants

```cpp
#define TOTAL_SLOTS 1
#define GATE_OPEN_ANGLE 95
#define GATE_CLOSE_ANGLE 0
#define GATE_OPEN_TIME 3000  // milliseconds
```
GATE_OPEN_TIME defines the minimum time the gate remains open after the vehicle leaves the IR sensor range.

The system can be easily extended to support multiple slots for future enhancement.

**📚 Required Libraries
**
Install via Arduino Library Manager:

LiquidCrystal_I2C

ESP32Servo

Adafruit GFX Library

Adafruit SSD1306

**🖥️ Serial Monitor Output
**
set Baud rate: 115200

_Logs:_

```text
=== Parking System Boot ===
[SLOT] Available: 1
[ENTRANCE] Car detected
[GATE] Opening
[GATE] Closed
```

**These logs are essential for:
**
```text
debugging sensor behavior

validating gate logic

live demonstrations
```

🧩 File Structure
```text
SmartParkingGate/
├─ SmartParkingGate.ino
├─ raspberry-pi/
│  └─ (AI model, database, and communication logic — Planned for Sprint 2)
├─ README.md
```

🚀 Future Improvements (Planned)

```text
Multi-slot support

RFID card support for non-member drivers

ESP32 → Raspberry Pi communication (HTTP / MQTT)

License plate capture & AI analysis

Database-backed parking sessions

Mobile / Web dashboard
```

📝 Notes

```text
This sketch runs only on the edge device (ESP32-S3)

Designed for clean integration with a Raspberry Pi backend

Modular code structure for easy expansion

No blocking delays — safe for real-time control
```
