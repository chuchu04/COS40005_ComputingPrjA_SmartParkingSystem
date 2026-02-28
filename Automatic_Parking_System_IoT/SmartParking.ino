#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

/* ===== PINS ===== */
#define IR_ENTRANCE 6
#define IR_SLOT     7
#define SERVO_PIN   5
#define SDA_PIN     8
#define SCL_PIN     9

/* ===== SYSTEM CONFIG ===== */
#define TOTAL_SLOTS 1
#define GATE_OPEN_ANGLE 95
#define GATE_CLOSE_ANGLE 0
#define GATE_OPEN_TIME 3000   // milliseconds
#define OLED_MSG_TIME 500     // non-blocking UI delay

/* ===== DISPLAYS ===== */
LiquidCrystal_I2C lcd(0x27, 16, 2);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

Servo gateServo;

/* ===== STATE ===== */
bool lastEntranceState = false;
bool gateOpen = false;
bool lastSlotOccupied = false;

int availableSlots = TOTAL_SLOTS;

unsigned long gateOpenMillis = 0;

/* OLED timing */
bool oledBusy = false;
unsigned long oledMillis = 0;

/* ================= SETUP ================= */

void setup() {
  pinMode(IR_ENTRANCE, INPUT);
  pinMode(IR_SLOT, INPUT);

  Serial.begin(115200);
  Serial.println("=== Parking System Boot ===");

  Wire.begin(SDA_PIN, SCL_PIN);

  lcd.init();
  lcd.backlight();

  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found");
    while (1);
  }

  oledMessage("System Ready");

  gateServo.attach(SERVO_PIN);
  gateServo.write(GATE_CLOSE_ANGLE);

  updateSlotLCD();
}

/* ================= LOOP ================= */

void loop() {
  handleSlot();
  handleEntrance();
  handleGateAutoClose();
  handleOLEDTimeout();
}

/* ================= SLOT LOGIC ================= */

void handleSlot() {
  bool slotOccupied = (digitalRead(IR_SLOT) == LOW);

  if (slotOccupied != lastSlotOccupied) {
    lastSlotOccupied = slotOccupied;
    availableSlots = slotOccupied ? 0 : 1;

    Serial.print("[SLOT] Available: ");
    Serial.println(availableSlots);

    updateSlotLCD();
  }
}

void updateSlotLCD() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Slot available:");
  lcd.setCursor(0, 1);
  lcd.print(availableSlots);
}

/* ================= ENTRANCE LOGIC ================= */

void handleEntrance() {
  bool entranceDetected = (digitalRead(IR_ENTRANCE) == LOW);

  if (entranceDetected && !lastEntranceState) {
    Serial.println("[ENTRANCE] Car detected");
    oledMessage("Car detected");

    if (availableSlots == 0) {
      Serial.println("[GATE] Parking full");

      // HIGH PRIORITY → override current OLED message
      oledMessage("Parking FULL");
    }
    else if (!gateOpen) {
      Serial.println("[GATE] Opening");
      queueOLEDMessage("Gate opening");

      gateServo.write(GATE_OPEN_ANGLE);
      gateOpen = true;
      gateOpenMillis = millis();
    }
  }

  lastEntranceState = entranceDetected;
}

/* ================= GATE AUTO CLOSE ================= */

void handleGateAutoClose() {
  if (gateOpen && millis() - gateOpenMillis >= GATE_OPEN_TIME) {
    gateServo.write(GATE_CLOSE_ANGLE);
    gateOpen = false;

    Serial.println("[GATE] Closed");
    oledMessage("Gate closed");
  }
}

/* ================= OLED HELPERS ================= */

void oledMessage(const char* msg) {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);

  int16_t x1, y1;
  uint16_t w, h;
  oled.getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);

  oled.setCursor((SCREEN_WIDTH - w) / 2, (SCREEN_HEIGHT - h) / 2);
  oled.println(msg);
  oled.display();

  oledBusy = true;
  oledMillis = millis();
}

void queueOLEDMessage(const char* msg) {
  if (!oledBusy) {
    oledMessage(msg);
  }
}

void handleOLEDTimeout() {
  if (oledBusy && millis() - oledMillis >= OLED_MSG_TIME) {
    oledBusy = false;
  }
}
