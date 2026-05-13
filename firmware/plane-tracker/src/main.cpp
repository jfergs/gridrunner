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
constexpr int SD_CS = 4;
constexpr int LCD_MISO = 5;
constexpr int BUTTON_PIN = 9;

constexpr int SCREEN_W = 172;
constexpr int SCREEN_H = 320;
constexpr int RADAR_CX = 86;
constexpr int RADAR_CY = 88;
constexpr int RADAR_R = 72;
constexpr size_t MAX_AIRCRAFT = 12;
constexpr size_t AIRCRAFT_ROWS_PER_PAGE = 5;
constexpr uint32_t MQTT_RECONNECT_MS = 3000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t DATA_STALE_MS = 30000;
constexpr uint32_t STATUS_REFRESH_MS = 5000;
constexpr uint32_t SWEEP_REFRESH_MS = 120;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 35;
constexpr uint32_t BUTTON_MULTI_TAP_MS = 360;
constexpr uint32_t BUTTON_LONG_PRESS_MS = 750;

constexpr uint16_t COLOR_BG = 0x0000;
constexpr uint16_t COLOR_GRID = 0x0320;
constexpr uint16_t COLOR_DIM = 0x0200;
constexpr uint16_t COLOR_TEXT = 0x07E0;
constexpr uint16_t COLOR_HOT = 0xFFE0;
constexpr uint16_t COLOR_WARN = 0xFBE0;
constexpr uint16_t COLOR_BAD = 0xF800;

constexpr uint8_t BRIGHTNESS_LEVELS[] = {0, 25, 50, 75, 100};
constexpr uint8_t DEFAULT_BRIGHTNESS_INDEX = 3;

enum class ViewMode {
  List,
  Detail,
};

struct Aircraft {
  String ident;
  String squawk;
  String category;
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
Arduino_DataBus *bus = new Arduino_HWSPI(LCD_DC, LCD_CS, LCD_SCLK, LCD_MOSI, LCD_MISO);
Arduino_GFX *panel = new Arduino_ST7789(bus, LCD_RST, 0, true, SCREEN_W, SCREEN_H, 34, 0, 34, 0);
Arduino_Canvas *gfx = new Arduino_Canvas(SCREEN_W, SCREEN_H, panel);

Aircraft aircraft[MAX_AIRCRAFT];
size_t aircraftCount = 0;
size_t selectedAircraft = 0;
int totalAircraft = 0;
int payloadAge = -1;
String trackerStatus = "boot";
uint32_t lastPayloadMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastFrameMs = 0;
uint32_t lastSweepMs = 0;
uint32_t payloadCount = 0;
int sweepDeg = 0;
ViewMode viewMode = ViewMode::List;
uint8_t brightnessIndex = DEFAULT_BRIGHTNESS_INDEX;
bool dirty = true;

bool buttonStablePressed = false;
bool buttonLastReading = false;
bool buttonLongHandled = false;
uint8_t pendingTapCount = 0;
uint32_t buttonLastChangeMs = 0;
uint32_t buttonPressedAtMs = 0;
uint32_t lastTapAtMs = 0;

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

String trimmedCopy(const String &value) {
  String copy = value;
  copy.trim();
  return copy;
}

String numberText(bool present, int value) {
  return present ? String(value) : "---";
}

void drawText(int16_t x, int16_t y, const String &text, uint16_t color, uint8_t size = 1) {
  gfx->setTextColor(color, COLOR_BG);
  gfx->setTextSize(size);
  gfx->setCursor(x, y);
  gfx->print(text);
}

void drawTextClipped(int16_t x, int16_t y, String text, size_t limit, uint16_t color, uint8_t size = 1) {
  if (text.length() > limit) {
    text = text.substring(0, limit);
  }
  drawText(x, y, text, color, size);
}

void applyBrightness() {
  uint32_t duty = map(BRIGHTNESS_LEVELS[brightnessIndex], 0, 100, 0, 255);
  ledcWrite(LCD_BL, duty);
}

void nextBrightness() {
  brightnessIndex = (brightnessIndex + 1) % (sizeof(BRIGHTNESS_LEVELS) / sizeof(BRIGHTNESS_LEVELS[0]));
  applyBrightness();
  dirty = true;
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  uint32_t now = millis();
  if (lastWifiAttemptMs != 0 && now - lastWifiAttemptMs < WIFI_RETRY_MS) {
    return;
  }
  lastWifiAttemptMs = now;
  trackerStatus = "wifi";

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.setMinSecurity(WIFI_AUTH_WPA2_PSK);
  WiFi.setScanMethod(WIFI_ALL_CHANNEL_SCAN);
  WiFi.setSortMethod(WIFI_CONNECT_AP_BY_SIGNAL);
  WiFi.begin(trimmedCopy(GRIDRUNNER_WIFI_SSID).c_str(), trimmedCopy(GRIDRUNNER_WIFI_PASSWORD).c_str());
  dirty = true;
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  (void)topic;

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    trackerStatus = "json";
    dirty = true;
    return;
  }

  const char *schema = doc["schema"] | "";
  if (String(schema) != "gridrunner.adsb.plane_tracker.v1") {
    trackerStatus = "schema";
    dirty = true;
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
    target.squawk = fieldText(row["squawk"], "");
    target.category = fieldText(row["category"], "");

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

  if (selectedAircraft >= aircraftCount) {
    selectedAircraft = aircraftCount == 0 ? 0 : aircraftCount - 1;
    viewMode = ViewMode::List;
  }

  lastPayloadMs = millis();
  payloadCount++;
  dirty = true;
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
  dirty = true;
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

void drawRadarGrid() {
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R, COLOR_GRID);
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R * 2 / 3, COLOR_GRID);
  gfx->drawCircle(RADAR_CX, RADAR_CY, RADAR_R / 3, COLOR_GRID);
  gfx->drawFastHLine(RADAR_CX - RADAR_R, RADAR_CY, RADAR_R * 2, COLOR_DIM);
  gfx->drawFastVLine(RADAR_CX, RADAR_CY - RADAR_R, RADAR_R * 2, COLOR_DIM);

  double angle = sweepDeg * DEG_TO_RAD;
  int16_t x = RADAR_CX + sin(angle) * RADAR_R;
  int16_t y = RADAR_CY - cos(angle) * RADAR_R;
  gfx->drawLine(RADAR_CX, RADAR_CY, x, y, COLOR_TEXT);
}

void drawAircraftBlips() {
  for (size_t i = 0; i < aircraftCount; ++i) {
    int16_t x = 0;
    int16_t y = 0;
    aircraftPoint(aircraft[i], i, x, y);
    uint16_t color = i == selectedAircraft ? COLOR_BAD : (aircraft[i].hasSeen && aircraft[i].seen > 20 ? COLOR_WARN : COLOR_HOT);
    gfx->fillCircle(x, y, i == selectedAircraft ? 4 : 3, color);
    gfx->drawPixel(x - 5, y, color);
    gfx->drawPixel(x + 5, y, color);
    gfx->drawPixel(x, y - 5, color);
    gfx->drawPixel(x, y + 5, color);
  }
}

void drawStatus() {
  bool stale = lastPayloadMs == 0 || millis() - lastPayloadMs > DATA_STALE_MS || trackerStatus != "present";
  uint16_t statusColor = stale ? COLOR_BAD : COLOR_TEXT;
  String age = payloadAge >= 0 ? String(payloadAge) + "s" : "---";
  size_t page = aircraftCount == 0 ? 1 : selectedAircraft / AIRCRAFT_ROWS_PER_PAGE + 1;
  size_t pages = aircraftCount == 0 ? 1 : (aircraftCount + AIRCRAFT_ROWS_PER_PAGE - 1) / AIRCRAFT_ROWS_PER_PAGE;
  String status = "A" + String(totalAircraft) + " " + age;
  status += WiFi.status() == WL_CONNECTED ? " W+" : " W-";
  status += mqtt.connected() ? " M+" : " M-";
  status += " B" + String(BRIGHTNESS_LEVELS[brightnessIndex]);
  status += viewMode == ViewMode::Detail ? " D" : " L";
  if (pages > 1) {
    status += " P" + String(page) + "/" + String(pages);
  }

  drawText(4, 308, status, statusColor);
}

void drawAircraftList() {
  int y = 168;
  drawText(6, y, "ID       ALT   SPD HDG", COLOR_TEXT);
  y += 14;

  size_t pageStart = selectedAircraft / AIRCRAFT_ROWS_PER_PAGE * AIRCRAFT_ROWS_PER_PAGE;
  for (size_t rowIndex = 0; rowIndex < AIRCRAFT_ROWS_PER_PAGE; ++rowIndex) {
    size_t i = pageStart + rowIndex;
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

    uint16_t color = i == selectedAircraft ? COLOR_HOT : (item.hasSeen && item.seen > 20 ? COLOR_WARN : COLOR_TEXT);
    drawText(6, y, row, color);
    y += 22;
  }
}

void drawAircraftDetail() {
  if (aircraftCount == 0) {
    drawText(16, 172, "NO AIRCRAFT", COLOR_WARN, 2);
    drawText(20, 204, "WAITING FOR ADS-B", COLOR_DIM);
    return;
  }

  const Aircraft &item = aircraft[selectedAircraft];
  int y = 166;
  drawTextClipped(6, y, item.ident, 12, COLOR_HOT, 2);
  y += 30;
  drawText(6, y, "ALT " + numberText(item.hasAltitude, item.altitude) + " FT", COLOR_TEXT);
  y += 18;
  drawText(6, y, "SPD " + numberText(item.hasSpeed, item.speed) + " KT", COLOR_TEXT);
  y += 18;
  drawText(6, y, "HDG " + numberText(item.hasTrack, item.track), COLOR_TEXT);
  y += 18;
  drawText(6, y, "SEEN " + numberText(item.hasSeen, item.seen) + " S", COLOR_TEXT);
  y += 18;
  drawText(6, y, "SQ " + (item.squawk.length() ? item.squawk : "---") + " CAT " + (item.category.length() ? item.category : "---"), COLOR_DIM);
  y += 18;
  if (item.hasLatLon) {
    drawText(6, y, String(item.lat, 4), COLOR_DIM);
    y += 14;
    drawText(6, y, String(item.lon, 4), COLOR_DIM);
  } else {
    drawText(6, y, "NO POSITION", COLOR_DIM);
  }
}

void drawOffline() {
  drawText(12, 120, "GRIDRUNNER", COLOR_TEXT, 2);
  drawText(16, 146, "ADS-B RADAR", COLOR_HOT);
  drawText(20, 180, WiFi.status() == WL_CONNECTED ? "MQTT LINK..." : "WIFI LINK...", COLOR_DIM);
}

void drawFrame() {
  gfx->fillScreen(COLOR_BG);
  drawStatus();

  if (WiFi.status() != WL_CONNECTED || !mqtt.connected()) {
    drawOffline();
  } else {
    drawRadarGrid();
    drawAircraftBlips();
    if (viewMode == ViewMode::Detail) {
      drawAircraftDetail();
    } else {
      drawAircraftList();
    }
  }

  gfx->flush();
  dirty = false;
  lastFrameMs = millis();
}

void selectNextAircraft() {
  if (aircraftCount == 0) {
    return;
  }
  selectedAircraft = (selectedAircraft + 1) % aircraftCount;
  dirty = true;
}

void enterDetail() {
  if (aircraftCount == 0) {
    return;
  }
  viewMode = ViewMode::Detail;
  dirty = true;
}

void enterList() {
  viewMode = ViewMode::List;
  dirty = true;
}

void handleTapSequence(uint8_t taps) {
  if (taps >= 3) {
    nextBrightness();
    return;
  }
  if (taps == 2) {
    enterList();
    return;
  }
  if (viewMode == ViewMode::Detail) {
    enterList();
  } else {
    selectNextAircraft();
  }
}

void pollButton() {
  uint32_t now = millis();
  bool readingPressed = digitalRead(BUTTON_PIN) == LOW;

  if (readingPressed != buttonLastReading) {
    buttonLastReading = readingPressed;
    buttonLastChangeMs = now;
  }

  if (now - buttonLastChangeMs >= BUTTON_DEBOUNCE_MS && readingPressed != buttonStablePressed) {
    buttonStablePressed = readingPressed;
    if (buttonStablePressed) {
      buttonPressedAtMs = now;
      buttonLongHandled = false;
    } else if (!buttonLongHandled) {
      pendingTapCount++;
      lastTapAtMs = now;
    }
  }

  if (buttonStablePressed && !buttonLongHandled && now - buttonPressedAtMs >= BUTTON_LONG_PRESS_MS) {
    buttonLongHandled = true;
    pendingTapCount = 0;
    enterDetail();
  }

  if (pendingTapCount > 0 && now - lastTapAtMs > BUTTON_MULTI_TAP_MS) {
    uint8_t taps = pendingTapCount;
    pendingTapCount = 0;
    handleTapSequence(taps);
  }
}

} // namespace

void setup() {
  Serial.begin(115200);
  pinMode(SD_CS, OUTPUT);
  digitalWrite(SD_CS, HIGH);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  ledcAttach(LCD_BL, 20000, 8);
  applyBrightness();

  if (!gfx->begin()) {
    panel->begin();
  }
  gfx->fillScreen(COLOR_BG);
  gfx->flush();

#ifdef GRIDRUNNER_LCD_DIAGNOSTIC
  drawText(12, 120, "LCD DIAG", COLOR_TEXT, 2);
  gfx->flush();
  return;
#endif

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  mqtt.setServer(GRIDRUNNER_MQTT_HOST, GRIDRUNNER_MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(12288);
  mqtt.setKeepAlive(30);
}

void loop() {
#ifdef GRIDRUNNER_LCD_DIAGNOSTIC
  return;
#endif

  pollButton();
  connectWifi();
  connectMqtt();
  mqtt.loop();

  if (millis() - lastFrameMs >= STATUS_REFRESH_MS) {
    dirty = true;
  }
  if (WiFi.status() == WL_CONNECTED && mqtt.connected() && millis() - lastSweepMs >= SWEEP_REFRESH_MS) {
    lastSweepMs = millis();
    sweepDeg = (sweepDeg + 6) % 360;
    dirty = true;
  }
  if (dirty) {
    drawFrame();
  }
}
