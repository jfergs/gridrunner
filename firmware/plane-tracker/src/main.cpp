#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include <PubSubClient.h>
#include <WiFi.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "config.example.h"
#endif

namespace {

constexpr int LCD_MOSI = 6;
constexpr int LCD_SCLK = 7;
constexpr int LCD_CS = 14;
constexpr int LCD_DC = 15;
constexpr int LCD_RST = 21;
constexpr int LCD_BL = 22;

constexpr int SCREEN_W = 172;
constexpr int SCREEN_H = 320;
constexpr int RADAR_CX = 86;
constexpr int RADAR_CY = 94;
constexpr int RADAR_R = 72;
constexpr size_t MAX_AIRCRAFT = 5;
constexpr uint32_t MQTT_RECONNECT_MS = 3000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t FRAME_MS = 80;
constexpr uint32_t DATA_STALE_MS = 30000;

constexpr uint16_t COLOR_BG = 0x0000;
constexpr uint16_t COLOR_GRID = 0x0320;
constexpr uint16_t COLOR_DIM = 0x0200;
constexpr uint16_t COLOR_TEXT = 0x07E0;
constexpr uint16_t COLOR_HOT = 0xFFE0;
constexpr uint16_t COLOR_WARN = 0xFBE0;
constexpr uint16_t COLOR_BAD = 0xF800;

struct Aircraft {
  String ident;
  bool hasAltitude = false;
  int altitude = 0;
  bool hasSpeed = false;
  int speed = 0;
  bool hasTrack = false;
  int track = 0;
  bool hasSeen = false;
  int seen = 0;
  bool hasLatLon = false;
  double lat = 0.0;
  double lon = 0.0;
};

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Arduino_DataBus *bus = new Arduino_ESP32SPI(LCD_DC, LCD_CS, LCD_SCLK, LCD_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_ST7789(bus, LCD_RST, 0, true, SCREEN_W, SCREEN_H, 34, 0, 34, 0);

Aircraft aircraft[MAX_AIRCRAFT];
size_t aircraftCount = 0;
int totalAircraft = 0;
int payloadAge = -1;
String trackerStatus = "boot";
uint32_t lastPayloadMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastFrameMs = 0;
int sweepDeg = 0;

String fieldText(JsonVariantConst value, const char *fallback = "---") {
  if (value.isNull()) {
    return fallback;
  }
  if (value.is<const char *>()) {
    const char *text = value.as<const char *>();
    return text && text[0] ? String(text) : String(fallback);
  }
  return value.as<String>();
}

String numberText(bool present, int value) {
  if (!present) {
    return "---";
  }
  return String(value);
}

void drawText(int16_t x, int16_t y, const String &text, uint16_t color, uint8_t size = 1) {
  gfx->setTextColor(color, COLOR_BG);
  gfx->setTextSize(size);
  gfx->setCursor(x, y);
  gfx->print(text);
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  uint32_t now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_MS) {
    return;
  }
  lastWifiAttemptMs = now;

  trackerStatus = "wifi";
  WiFi.mode(WIFI_STA);
  WiFi.begin(GRIDRUNNER_WIFI_SSID, GRIDRUNNER_WIFI_PASSWORD);
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  (void)topic;

  StaticJsonDocument<6144> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    trackerStatus = "json";
    return;
  }

  const char *schema = doc["schema"] | "";
  if (String(schema) != "gridrunner.adsb.plane_tracker.v1") {
    trackerStatus = "schema";
    return;
  }

  trackerStatus = doc["status"] | "unknown";
  totalAircraft = doc["count"] | 0;
  payloadAge = doc["age_seconds"].isNull() ? -1 : doc["age_seconds"].as<int>();
  aircraftCount = 0;

  JsonArrayConst rows = doc["aircraft"].as<JsonArrayConst>();
  for (JsonObjectConst row : rows) {
    if (aircraftCount >= MAX_AIRCRAFT) {
      break;
    }

    Aircraft &target = aircraft[aircraftCount++];
    target = Aircraft();
    target.ident = fieldText(row["ident"]);

    if (!row["altitude"].isNull()) {
      target.hasAltitude = true;
      target.altitude = row["altitude"].as<int>();
    }
    if (!row["speed"].isNull()) {
      target.hasSpeed = true;
      target.speed = row["speed"].as<int>();
    }
    if (!row["track"].isNull()) {
      target.hasTrack = true;
      target.track = row["track"].as<int>();
    }
    if (!row["seen_seconds"].isNull()) {
      target.hasSeen = true;
      target.seen = row["seen_seconds"].as<int>();
    }
    if (!row["lat"].isNull() && !row["lon"].isNull()) {
      target.hasLatLon = true;
      target.lat = row["lat"].as<double>();
      target.lon = row["lon"].as<double>();
    }
  }

  lastPayloadMs = millis();
}

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) {
    return;
  }

  uint32_t now = millis();
  if (now - lastMqttAttemptMs < MQTT_RECONNECT_MS) {
    return;
  }
  lastMqttAttemptMs = now;

  trackerStatus = "mqtt";
  String clientId = "gridrunner-plane-display-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (mqtt.connect(clientId.c_str())) {
    mqtt.subscribe(GRIDRUNNER_MQTT_TOPIC);
    trackerStatus = "linked";
  }
}

void drawRadarGrid() {
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R, COLOR_GRID);
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R * 2 / 3, COLOR_GRID);
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R / 3, COLOR_GRID);
  gfx->drawFastHLine(RADAR_CX - RADAR_R, RADAR_CY, RADAR_R * 2, COLOR_DIM);
  gfx->drawFastVLine(RADAR_CX, RADAR_CY - RADAR_R, RADAR_R * 2, COLOR_DIM);
}

void aircraftPoint(const Aircraft &item, int index, int16_t &x, int16_t &y) {
  double angle = item.hasTrack ? item.track * DEG_TO_RAD : (index * 72 + 20) * DEG_TO_RAD;
  double radius = RADAR_R * 0.55;

#if GRIDRUNNER_HAS_HOME_POSITION
  if (item.hasLatLon) {
    double latKm = (item.lat - GRIDRUNNER_HOME_LAT) * 111.0;
    double lonKm = (item.lon - GRIDRUNNER_HOME_LON) * 111.0 * cos(GRIDRUNNER_HOME_LAT * DEG_TO_RAD);
    double rangeKm = sqrt(latKm * latKm + lonKm * lonKm);
    angle = atan2(lonKm, -latKm);
    radius = min<double>(RADAR_R - 4, max<double>(10, rangeKm * 2.2));
  }
#else
  if (item.hasAltitude) {
    radius = 16 + min<double>(RADAR_R - 20, item.altitude / 600.0);
  }
#endif

  x = RADAR_CX + sin(angle) * radius;
  y = RADAR_CY - cos(angle) * radius;
}

void drawAircraftBlips() {
  for (size_t i = 0; i < aircraftCount; ++i) {
    int16_t x = 0;
    int16_t y = 0;
    aircraftPoint(aircraft[i], i, x, y);
    uint16_t color = aircraft[i].hasSeen && aircraft[i].seen > 20 ? COLOR_WARN : COLOR_HOT;
    gfx->fillCircle(x, y, 3, color);
    gfx->drawPixel(x - 4, y, color);
    gfx->drawPixel(x + 4, y, color);
    gfx->drawPixel(x, y - 4, color);
    gfx->drawPixel(x, y + 4, color);
  }
}

void drawSweep() {
  double angle = sweepDeg * DEG_TO_RAD;
  int16_t x = RADAR_CX + sin(angle) * RADAR_R;
  int16_t y = RADAR_CY - cos(angle) * RADAR_R;
  gfx->drawLine(RADAR_CX, RADAR_CY, x, y, COLOR_TEXT);
  sweepDeg = (sweepDeg + 4) % 360;
}

void drawAircraftList() {
  int y = 184;
  drawText(6, y, "ID       ALT   SPD HDG", COLOR_DIM);
  y += 14;

  for (size_t i = 0; i < MAX_AIRCRAFT; ++i) {
    if (i >= aircraftCount) {
      drawText(6, y, "--       ---   --- ---", COLOR_DIM);
      y += 22;
      continue;
    }

    const Aircraft &item = aircraft[i];
    String ident = item.ident;
    if (ident.length() > 7) {
      ident = ident.substring(0, 7);
    }
    while (ident.length() < 7) {
      ident += " ";
    }

    String row = ident + " " + numberText(item.hasAltitude, item.altitude);
    while (row.length() < 15) {
      row += " ";
    }
    row += numberText(item.hasSpeed, item.speed);
    while (row.length() < 21) {
      row += " ";
    }
    row += numberText(item.hasTrack, item.track);

    uint16_t color = item.hasSeen && item.seen > 20 ? COLOR_WARN : COLOR_TEXT;
    drawText(6, y, row, color);
    y += 22;
  }
}

void drawStatus() {
  bool stale = lastPayloadMs == 0 || millis() - lastPayloadMs > DATA_STALE_MS || trackerStatus != "present";
  uint16_t statusColor = stale ? COLOR_BAD : COLOR_TEXT;
  String age = payloadAge >= 0 ? String(payloadAge) + "s" : "---";

  drawText(6, 6, "GRIDRUNNER ADS-B", COLOR_TEXT);
  drawText(6, 20, "AIR " + String(totalAircraft), COLOR_HOT);
  drawText(72, 20, "AGE " + age, statusColor);
  drawText(6, 306, WiFi.status() == WL_CONNECTED ? "WIFI OK" : "WIFI ...", COLOR_DIM);
  drawText(76, 306, mqtt.connected() ? "MQTT OK" : "MQTT ...", COLOR_DIM);
}

void drawFrame() {
  gfx->fillScreen(COLOR_BG);
  drawStatus();
  drawRadarGrid();
  drawSweep();
  drawAircraftBlips();
  drawAircraftList();
}

} // namespace

void setup() {
  Serial.begin(115200);
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);

  gfx->begin();
  gfx->fillScreen(COLOR_BG);
  drawText(12, 120, "GRIDRUNNER", COLOR_TEXT, 2);
  drawText(16, 146, "ADS-B RADAR", COLOR_HOT, 1);

  mqtt.setServer(GRIDRUNNER_MQTT_HOST, GRIDRUNNER_MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(6144);
  connectWifi();
}

void loop() {
  connectWifi();
  connectMqtt();
  mqtt.loop();

  uint32_t now = millis();
  if (now - lastFrameMs >= FRAME_MS) {
    lastFrameMs = now;
    drawFrame();
  }
}
