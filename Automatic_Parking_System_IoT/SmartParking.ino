#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

/* ===== PINS ===== */
#define IR_ENTRANCE        6
#define IR_SLOT            7
#define IR_EXIT            11
#define SERVO_ENTRANCE_PIN 5
#define SERVO_EXIT2_PIN    4
#define SERVO_EXIT3_PIN    10
#define SDA_PIN            8
#define SCL_PIN            9

/* ===== SYSTEM CONFIG ===== */
#define TOTAL_SLOTS            1
#define GATE_OPEN_ANGLE        95
#define GATE_CLOSE_ANGLE       0
#define ENTRANCE_OPEN_TIME     5000   // ms — Servo 1 auto close
#define EXIT2_OPEN_TIME        5000   // ms — Servo 2 auto close
#define EXIT3_OPEN_TIME        5000   // ms — Servo 3 auto close
#define EXIT_COOLDOWN_TIME     5000   // ms — cooldown after Servo 3 closes
#define OLED_MSG_TIME          2000   // ms — OLED message duration
#define DEBOUNCE_MS            50     // ms — IR debounce window
#define MQTT_RETRY_INTERVAL    5000   // ms — MQTT retry interval
#define WIFI_CHECK_INTERVAL    10000  // ms — WiFi health check
#define WAITING_PRINT_INTERVAL 5000   // ms — throttle "car waiting" print

/* ===== SLOT ID ===== */
#define SLOT_ID "A1"

/* ===== DISPLAYS ===== */
LiquidCrystal_I2C lcd(0x27, 16, 2);

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

/* ===== SERVOS ===== */
Servo entranceServo;   // Servo 1 — entrance gate
Servo exit2Servo;      // Servo 2 — inner exit gate
Servo exit3Servo;      // Servo 3 — outer exit gate

/* ===== WIFI CONFIG ===== */
const char* ssid     = "Ve Que Ngoai";
const char* password = "nth1978@@";

/* ===== MQTT CONFIG ===== */
#define USE_SSL true

const char* mqtt_server = "g1cf0fc0.ala.asia-southeast1.emqxsl.com";
const int   mqtt_port   = 8883;
const char* mqtt_user   = "test";
const char* mqtt_pass   = "1";
const char* mqtt_client = "ParkingSlot";

#if USE_SSL
  WiFiClientSecure espClient;
#else
  WiFiClient espClient;
#endif

PubSubClient client(espClient);

/* ===== STATE ===== */
// Slot availability — controlled by IR_SLOT ONLY
int availableSlots = TOTAL_SLOTS;

// Entrance gate — Servo 1
bool entranceGateOpen            = false;
unsigned long entranceGateMillis = 0;

// Exit inner gate — Servo 2
bool exit2GateOpen            = false;
unsigned long exit2GateMillis = 0;

// Exit outer gate — Servo 3
bool exit3GateOpen            = false;
unsigned long exit3GateMillis = 0;

// Exit zone state
bool zoneBusy                    = false;
bool exitCooldownActive          = false;
unsigned long exitCooldownMillis = 0;

// Slot IR — debounced
bool lastSlotOccupied            = false;
bool rawSlotState                = false;
unsigned long slotDebounceMillis = 0;

// Entrance IR — debounced
bool lastEntranceState               = false;
bool rawEntranceState                = false;
unsigned long entranceDebounceMillis = 0;

// Exit IR — debounced (level-triggered, not edge)
bool exitIRActive                = false;
bool rawExitState                = false;
unsigned long exitDebounceMillis = 0;

// OLED
bool oledBusy           = false;
unsigned long oledMillis = 0;

// Timers
unsigned long lastMQTTAttempt  = 0;
unsigned long lastWiFiCheck    = 0;
unsigned long lastWaitingPrint = 0;

/* ============================================================
 *  FORWARD DECLARATIONS
 * ============================================================ */
void onMQTTMessage(char* topic, byte* payload, unsigned int length);

/* ============================================================
 *  SETUP
 * ============================================================ */
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Smart Parking System Boot ===");

  pinMode(IR_ENTRANCE, INPUT);
  pinMode(IR_SLOT,     INPUT);
  pinMode(IR_EXIT,     INPUT);

  /* WiFi FIRST */
  setupWiFi();

  /* MQTT */
  #if USE_SSL
    espClient.setInsecure();
  #endif
  client.setServer(mqtt_server, mqtt_port);
  client.setBufferSize(512);
  client.setCallback(onMQTTMessage);

  /* Hardware */
  Wire.begin(SDA_PIN, SCL_PIN);

  lcd.init();
  lcd.backlight();
  lcdMessage("Initialising...", "");

  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ERROR] OLED not found");
    while (1) delay(100);
  }
  oledMessage("Booting...");

  /* All servos start closed */
  entranceServo.attach(SERVO_ENTRANCE_PIN);
  entranceServo.write(GATE_CLOSE_ANGLE);
  Serial.println("[SERVO 1] Entrance — closed");

  exit2Servo.attach(SERVO_EXIT2_PIN);
  exit2Servo.write(GATE_CLOSE_ANGLE);
  Serial.println("[SERVO 2] Exit inner — closed");

  exit3Servo.attach(SERVO_EXIT3_PIN);
  exit3Servo.write(GATE_CLOSE_ANGLE);
  Serial.println("[SERVO 3] Exit outer — closed");

  updateSlotLCD();
  oledMessage("System Ready");
  Serial.println("[BOOT] Complete");
}

/* ============================================================
 *  LOOP
 * ============================================================ */
void loop() {
  maintainWiFi();
  maintainMQTT();

  handleSlot();
  handleEntrance();
  handleEntranceAutoClose();
  handleExit();
  handleExit2AutoClose();
  handleExit3AutoClose();
  handleExitCooldown();
  handleOLEDTimeout();
}

/* ============================================================
 *  WIFI
 * ============================================================ */
void setupWiFi() {
  Serial.printf("[WiFi] Connecting to \"%s\" ", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 30000) {
      Serial.println("\n[WiFi] Timeout — continuing offline");
      return;
    }
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.printf("[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
}

void maintainWiFi() {
  if (millis() - lastWiFiCheck < WIFI_CHECK_INTERVAL) return;
  lastWiFiCheck = millis();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Lost — reconnecting...");
    WiFi.reconnect();
  }
}

/* ============================================================
 *  MQTT
 * ============================================================ */
void maintainMQTT() {
  if (WiFi.status() != WL_CONNECTED) return;

  if (client.connected()) {
    client.loop();
    return;
  }

  if (millis() - lastMQTTAttempt < MQTT_RETRY_INTERVAL) return;
  lastMQTTAttempt = millis();

  Serial.println("[MQTT] Attempting connection...");

  bool connected = (strlen(mqtt_user) > 0)
    ? client.connect(mqtt_client, mqtt_user, mqtt_pass)
    : client.connect(mqtt_client);

  if (connected) {
    Serial.println("[MQTT] Connected");
    bool ok = client.subscribe("parking/gate/exit");
    Serial.printf("[MQTT] Subscribed parking/gate/exit: %s\n", ok ? "OK" : "FAILED");
  } else {
    Serial.printf("[MQTT] Failed — rc=%d — retry in %d s\n",
                  client.state(), MQTT_RETRY_INTERVAL / 1000);
  }
}

void mqttPublish(const char* topic, const char* payload) {
  if (client.connected()) {
    client.publish(topic, payload);
    Serial.printf("[MQTT] Published  %s → %s\n", topic, payload);
  } else {
    Serial.printf("[MQTT] Offline — skipped  %s → %s\n", topic, payload);
  }
}

/* ============================================================
 *  MQTT INCOMING — payment result from Friend B
 *
 *  Topic:   parking/gate/exit
 *  Payload: "PAID"   → open Servo 3, car exits
 *           "UNPAID" → re-open Servo 2, car returns to slot
 * ============================================================ */
void onMQTTMessage(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  msg.toUpperCase();

  Serial.printf("[MQTT] Received  %s → %s\n", topic, msg.c_str());

  if (String(topic) != "parking/gate/exit") return;

  if (msg == "PAID") {
    Serial.println("[EXIT] Payment confirmed — opening Servo 3");
    exit3Servo.write(GATE_OPEN_ANGLE);
    exit3GateOpen   = true;
    exit3GateMillis = millis();
    oledMessage("Payment OK!");
  }
  else if (msg == "UNPAID") {
    Serial.println("[EXIT] UNPAID — Servo 2 re-opening, car returns to slot");
    oledMessage("Insuff. Balance!");

    exit2Servo.write(GATE_OPEN_ANGLE);
    exit2GateOpen   = true;
    exit2GateMillis = millis();
    zoneBusy        = false;
  }
  else {
    Serial.printf("[MQTT] Unknown payload: %s\n", msg.c_str());
  }
}

/* ============================================================
 *  SLOT LOGIC  (IR_SLOT — debounced)
 *  SOLE controller of availableSlots and slot MQTT topic
 *
 *  Topic:   parking/sensor/sonar
 *  Payload: {"slotId": "A1", "isOccupied": true/false}
 * ============================================================ */
void handleSlot() {
  bool reading = (digitalRead(IR_SLOT) == LOW);

  if (reading != rawSlotState) {
    rawSlotState = reading;
    slotDebounceMillis = millis();
  }

  if (millis() - slotDebounceMillis < DEBOUNCE_MS) return;

  bool slotOccupied = rawSlotState;

  if (slotOccupied == lastSlotOccupied) return;
  lastSlotOccupied = slotOccupied;

  availableSlots = slotOccupied ? 0 : TOTAL_SLOTS;

  Serial.printf("[SLOT] %s — available: %d\n",
                slotOccupied ? "Occupied" : "Free", availableSlots);

  String payload = "{\"slotId\": \"" SLOT_ID "\", \"isOccupied\": ";
  payload += slotOccupied ? "true" : "false";
  payload += "}";

  mqttPublish("parking/sensor/sonar", payload.c_str());
  updateSlotLCD();
  oledMessage(slotOccupied ? "Slot Occupied" : "Slot Free");
}

void updateSlotLCD() {
  if (availableSlots > 0) {
    lcdMessage("Slots available:", String(availableSlots).c_str());
  } else {
    lcdMessage("Parking is", "FULL");
  }
}

/* ============================================================
 *  ENTRANCE LOGIC  (IR_ENTRANCE — debounced, edge-triggered)
 *  Servo 1 only — no MQTT control
 *  Does NOT touch availableSlots — IR_SLOT handles that
 *
 *  Publishes: parking/camera/entrance → {"status": "detected"}
 * ============================================================ */
void handleEntrance() {
  bool reading = (digitalRead(IR_ENTRANCE) == LOW);

  if (reading != rawEntranceState) {
    rawEntranceState = reading;
    entranceDebounceMillis = millis();
  }

  if (millis() - entranceDebounceMillis < DEBOUNCE_MS) return;

  bool entranceDetected = rawEntranceState;

  /* Rising edge only — car just arrived */
  if (!entranceDetected || lastEntranceState) {
    lastEntranceState = entranceDetected;
    return;
  }
  lastEntranceState = true;

  Serial.println("[ENTRANCE] Car detected");

  if (availableSlots == 0) {
    Serial.println("[SERVO 1] Lot full — staying closed");
    oledMessage("Parking FULL!");
    return;
  }

  if (entranceGateOpen) {
    Serial.println("[SERVO 1] Already open — ignoring");
    return;
  }

  /* Open Servo 1 */
  Serial.println("[SERVO 1] Opening");
  entranceServo.write(GATE_OPEN_ANGLE);
  entranceGateOpen   = true;
  entranceGateMillis = millis();
  oledMessage("Welcome!");

  /* Trigger Friend A entrance scan */
  mqttPublish("parking/camera/entrance", "{\"status\": \"detected\"}");
}

void handleEntranceAutoClose() {
  if (!entranceGateOpen) return;
  if (millis() - entranceGateMillis < ENTRANCE_OPEN_TIME) return;

  entranceServo.write(GATE_CLOSE_ANGLE);
  entranceGateOpen = false;
  Serial.println("[SERVO 1] Auto-closed");
}

/* ============================================================
 *  EXIT LOGIC  (IR_EXIT — level-triggered, stays on while car waits)
 *  Servo 2 — inner exit gate
 *
 *  Publishes: parking/camera/exit → {"status": "detected"}
 * ============================================================ */
void handleExit() {
  bool reading = (digitalRead(IR_EXIT) == LOW);

  if (reading != rawExitState) {
    rawExitState = reading;
    exitDebounceMillis = millis();
  }

  if (millis() - exitDebounceMillis < DEBOUNCE_MS) return;

  exitIRActive = rawExitState;

  // No car at exit IR — nothing to do
  if (!exitIRActive) return;

  // Car waiting but zone busy or cooldown active — hold
  if (zoneBusy || exitCooldownActive) {
    if (millis() - lastWaitingPrint >= WAITING_PRINT_INTERVAL) {
      lastWaitingPrint = millis();
      Serial.println("[EXIT] Car waiting in queue...");
    }
    return;
  }

  // Servo 2 already open — ignore
  if (exit2GateOpen) return;

  /* Zone FREE + car detected — open Servo 2 */
  Serial.println("[SERVO 2] Opening — car entering camera zone");
  exit2Servo.write(GATE_OPEN_ANGLE);
  exit2GateOpen   = true;
  exit2GateMillis = millis();
  zoneBusy        = true;
  oledMessage("Scanning...");

  /* Trigger Friend A exit scan */
  mqttPublish("parking/camera/exit", "{\"status\": \"detected\"}");
}

void handleExit2AutoClose() {
  if (!exit2GateOpen) return;
  if (millis() - exit2GateMillis < EXIT2_OPEN_TIME) return;

  exit2Servo.write(GATE_CLOSE_ANGLE);
  exit2GateOpen = false;
  Serial.println("[SERVO 2] Auto-closed — car in camera zone");
}

/* ============================================================
 *  EXIT OUTER GATE AUTO-CLOSE  (Servo 3)
 *  After Servo 3 opens (PAID), auto-close then start cooldown
 * ============================================================ */
void handleExit3AutoClose() {
  if (!exit3GateOpen) return;
  if (millis() - exit3GateMillis < EXIT3_OPEN_TIME) return;

  exit3Servo.write(GATE_CLOSE_ANGLE);
  exit3GateOpen = false;
  Serial.println("[SERVO 3] Auto-closed — starting 5s cooldown");

  exitCooldownActive = true;
  exitCooldownMillis = millis();
}

/* ============================================================
 *  EXIT COOLDOWN — 5s after Servo 3 closes
 *  Prevents next car entering zone before previous car clears
 * ============================================================ */
void handleExitCooldown() {
  if (!exitCooldownActive) return;
  if (millis() - exitCooldownMillis < EXIT_COOLDOWN_TIME) return;

  exitCooldownActive = false;
  zoneBusy           = false;
  Serial.println("[ZONE] FREE — cooldown complete");

  // If car still waiting at IR, open Servo 2 immediately
  if (exitIRActive) {
    Serial.println("[SERVO 2] Next car waiting — opening immediately");
    exit2Servo.write(GATE_OPEN_ANGLE);
    exit2GateOpen   = true;
    exit2GateMillis = millis();
    zoneBusy        = true;
    oledMessage("Scanning...");
    mqttPublish("parking/camera/exit", "{\"status\": \"detected\"}");
  }
}

/* ============================================================
 *  OLED HELPERS
 * ============================================================ */
void oledMessage(const char* msg) {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);

  int16_t  x1, y1;
  uint16_t w, h;
  oled.getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);
  oled.setCursor((SCREEN_WIDTH - w) / 2, (SCREEN_HEIGHT - h) / 2);
  oled.println(msg);
  oled.display();

  oledBusy   = true;
  oledMillis = millis();
}

void handleOLEDTimeout() {
  if (oledBusy && millis() - oledMillis >= OLED_MSG_TIME) {
    oledBusy = false;
  }
}

/* ============================================================
 *  LCD HELPERS
 * ============================================================ */
void lcdMessage(const char* line1, const char* line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}
