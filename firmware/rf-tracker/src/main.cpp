#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include <BLEDevice.h>
#include <PubSubClient.h>
#include <WiFi.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "config.example.h"
#endif

#ifndef GRIDRUNNER_NODE_ID
#define GRIDRUNNER_NODE_ID "c6-rf-tracker-01"
#endif
#ifndef GRIDRUNNER_TRACKER_PROFILE
#define GRIDRUNNER_TRACKER_PROFILE "rf-handheld"
#endif
#ifndef GRIDRUNNER_WIFI_SCAN_INTERVAL_MS
#define GRIDRUNNER_WIFI_SCAN_INTERVAL_MS 15000
#endif
#ifndef GRIDRUNNER_BLE_SCAN_INTERVAL_MS
#define GRIDRUNNER_BLE_SCAN_INTERVAL_MS 30000
#endif
#ifndef GRIDRUNNER_BLE_SCAN_SECONDS
#define GRIDRUNNER_BLE_SCAN_SECONDS 2
#endif
#ifndef GRIDRUNNER_BLE_IGNORE_RSSI_BELOW
#define GRIDRUNNER_BLE_IGNORE_RSSI_BELOW -95
#endif
#ifndef GRIDRUNNER_TELEMETRY_INTERVAL_MS
#define GRIDRUNNER_TELEMETRY_INTERVAL_MS 10000
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
constexpr size_t MAX_APS = 12;
constexpr size_t AP_ROWS_PER_PAGE = 5;
constexpr uint32_t MQTT_RECONNECT_MS = 3000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t WIFI_SCAN_TIMEOUT_MS = 8000;
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

struct AccessPoint {
  String ssid;
  int32_t rssi = -127;
  int32_t channel = 0;
  uint8_t encryption = 0;
  bool hidden = false;
  bool droneCandidate = false;
};

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Arduino_DataBus *bus = new Arduino_HWSPI(LCD_DC, LCD_CS, LCD_SCLK, LCD_MOSI, LCD_MISO);
Arduino_GFX *panel = new Arduino_ST7789(bus, LCD_RST, 0, true, SCREEN_W, SCREEN_H, 34, 0, 34, 0);
Arduino_Canvas *gfx = new Arduino_Canvas(SCREEN_W, SCREEN_H, panel);

AccessPoint accessPoints[MAX_APS];
size_t apCount = 0;
size_t totalAps = 0;
size_t selectedAp = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastFrameMs = 0;
uint32_t lastSweepMs = 0;
uint32_t lastScanMs = 0;
uint32_t lastTelemetryMs = 0;
uint32_t lastTelemetryOkMs = 0;
uint32_t scanCount = 0;
uint32_t pendingTelemetryScans = 0;
int sweepDeg = 0;
int strongestRssi = -127;
String strongestSsid = "";
String trackerStatus = "boot";
ViewMode viewMode = ViewMode::List;
uint8_t brightnessIndex = DEFAULT_BRIGHTNESS_INDEX;
bool dirty = true;
bool wifiScanInProgress = false;
bool bleScanInProgress = false;
BLEScan *bleScan = nullptr;
uint32_t wifiScanStartedMs = 0;
uint32_t lastBleScanMs = 0;
uint32_t bleScanStartedMs = 0;
uint32_t bleScanCount = 0;
int bleKnownCount = 0;
int bleUnknownCount = 0;
int bleIgnoredCount = 0;
int bleRssiPeak = 0;
int droneCandidateCount = 0;
int droneWifiCount = 0;
int droneBleCount = 0;
int droneRssiPeak = 0;
int droneWifiRssiPeak = 0;
int droneBleRssiPeak = 0;

bool buttonStablePressed = false;
bool buttonLastReading = false;
bool buttonLongHandled = false;
uint8_t pendingTapCount = 0;
uint32_t buttonLastChangeMs = 0;
uint32_t buttonPressedAtMs = 0;
uint32_t lastTapAtMs = 0;

void bleScanComplete(BLEScanResults results);

String trimmedCopy(const String &value) {
  String copy = value;
  copy.trim();
  return copy;
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

String mqttTopic() {
  return "gridrunner/nodes/" + String(GRIDRUNNER_NODE_ID) + "/telemetry";
}

String lowerCopy(String value) {
  value.toLowerCase();
  return value;
}

bool textSuggestsDrone(const String &value) {
  String lower = lowerCopy(value);
  return lower.indexOf("drone") >= 0 || lower.indexOf("opendroneid") >= 0 ||
         lower.indexOf("remoteid") >= 0 || lower.indexOf("remote-id") >= 0 ||
         lower.indexOf("open drone id") >= 0 || lower.indexOf("uav") >= 0 ||
         lower.indexOf("dji") >= 0 || lower.indexOf("autel") >= 0 ||
         lower.indexOf("skydio") >= 0 || lower.indexOf("parrot") >= 0;
}

bool uuidSuggestsRemoteId(const BLEUUID &uuid) {
  String text = lowerCopy(uuid.toString());
  return text.indexOf("fffa") >= 0 || text.indexOf("opendroneid") >= 0;
}

bool bleSuggestsDrone(BLEAdvertisedDevice &device) {
  if (device.haveName() && textSuggestsDrone(device.getName())) {
    return true;
  }
  if (device.haveManufacturerData() && textSuggestsDrone(device.getManufacturerData())) {
    return true;
  }
  if (device.haveServiceData() && textSuggestsDrone(device.getServiceData())) {
    return true;
  }
  for (int i = 0; i < device.getServiceUUIDCount(); ++i) {
    if (uuidSuggestsRemoteId(device.getServiceUUID(i))) {
      return true;
    }
  }
  for (int i = 0; i < device.getServiceDataUUIDCount(); ++i) {
    if (uuidSuggestsRemoteId(device.getServiceDataUUID(i))) {
      return true;
    }
  }
  return false;
}

void refreshDroneSummary() {
  droneCandidateCount = droneWifiCount + droneBleCount;
  if (droneWifiRssiPeak == 0) {
    droneRssiPeak = droneBleRssiPeak;
  } else if (droneBleRssiPeak == 0) {
    droneRssiPeak = droneWifiRssiPeak;
  } else {
    droneRssiPeak = max(droneWifiRssiPeak, droneBleRssiPeak);
  }
}

void recordDroneCandidate(int rssi, bool fromWifi) {
  if (fromWifi) {
    droneWifiCount++;
    if (droneWifiRssiPeak == 0 || rssi > droneWifiRssiPeak) {
      droneWifiRssiPeak = rssi;
    }
  } else {
    droneBleCount++;
    if (droneBleRssiPeak == 0 || rssi > droneBleRssiPeak) {
      droneBleRssiPeak = rssi;
    }
  }
  refreshDroneSummary();
}

bool scanBusy() {
  return wifiScanInProgress || bleScanInProgress;
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED || scanBusy()) {
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
  String clientId = String(GRIDRUNNER_NODE_ID) + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (mqtt.connect(clientId.c_str())) {
    trackerStatus = "linked";
  }
  dirty = true;
}

String encryptionText(uint8_t encryption) {
  switch (encryption) {
    case WIFI_AUTH_OPEN:
      return "OPEN";
    case WIFI_AUTH_WEP:
      return "WEP";
    case WIFI_AUTH_WPA_PSK:
      return "WPA";
    case WIFI_AUTH_WPA2_PSK:
      return "WPA2";
    case WIFI_AUTH_WPA_WPA2_PSK:
      return "MIX";
    case WIFI_AUTH_WPA2_ENTERPRISE:
      return "ENT";
    case WIFI_AUTH_WPA3_PSK:
      return "WPA3";
    case WIFI_AUTH_WPA2_WPA3_PSK:
      return "23";
    default:
      return "SEC";
  }
}

void sortAccessPoints() {
  for (size_t i = 0; i < apCount; ++i) {
    for (size_t j = i + 1; j < apCount; ++j) {
      if (accessPoints[j].rssi > accessPoints[i].rssi) {
        AccessPoint temp = accessPoints[i];
        accessPoints[i] = accessPoints[j];
        accessPoints[j] = temp;
      }
    }
  }
}

void finishWifiScan(int found) {
  totalAps = found > 0 ? static_cast<size_t>(found) : 0;
  apCount = 0;
  strongestRssi = -127;
  strongestSsid = "";
  droneWifiCount = 0;
  droneWifiRssiPeak = 0;
  refreshDroneSummary();

  if (found > 0) {
    for (int i = 0; i < found && apCount < MAX_APS; ++i) {
      AccessPoint &target = accessPoints[apCount++];
      target.ssid = WiFi.SSID(i);
      target.hidden = target.ssid.length() == 0;
      if (target.hidden) {
        target.ssid = "<hidden>";
      }
      target.rssi = WiFi.RSSI(i);
      target.channel = WiFi.channel(i);
      target.encryption = static_cast<uint8_t>(WiFi.encryptionType(i));
      target.droneCandidate = textSuggestsDrone(target.ssid);
      if (target.droneCandidate) {
        recordDroneCandidate(target.rssi, true);
      }

      if (target.rssi > strongestRssi) {
        strongestRssi = target.rssi;
        strongestSsid = target.ssid;
      }
    }
    sortAccessPoints();
  }

  if (selectedAp >= apCount) {
    selectedAp = apCount == 0 ? 0 : apCount - 1;
    viewMode = ViewMode::List;
  }

  WiFi.scanDelete();
  scanCount++;
  pendingTelemetryScans++;
  lastScanMs = millis();
  trackerStatus = mqtt.connected() ? "linked" : "local";
  wifiScanInProgress = false;
  dirty = true;
}

void scanWifi() {
  uint32_t now = millis();
  if (wifiScanInProgress) {
    int complete = WiFi.scanComplete();
    if (complete >= 0) {
      finishWifiScan(complete);
    } else if (complete == WIFI_SCAN_FAILED || now - wifiScanStartedMs > WIFI_SCAN_TIMEOUT_MS) {
      WiFi.scanDelete();
      wifiScanInProgress = false;
      lastScanMs = now;
      trackerStatus = "wifi-timeout";
      dirty = true;
    }
    return;
  }

  if (bleScanInProgress || (lastScanMs != 0 && now - lastScanMs < GRIDRUNNER_WIFI_SCAN_INTERVAL_MS)) {
    return;
  }

  int started = WiFi.scanNetworks(true, true, false, 120);
  if (started == WIFI_SCAN_RUNNING) {
    wifiScanInProgress = true;
    wifiScanStartedMs = now;
    trackerStatus = "wifi-scan";
  } else if (started >= 0) {
    finishWifiScan(started);
    return;
  } else {
    lastScanMs = now;
    trackerStatus = "wifi-scan-fail";
  }
  dirty = true;
}

void finishBleScan(BLEScanResults *results) {
  int known = 0;
  int unknown = 0;
  int ignored = 0;
  int peak = -127;
  droneBleCount = 0;
  droneBleRssiPeak = 0;
  refreshDroneSummary();

  int resultCount = results == nullptr ? 0 : results->getCount();
  for (int i = 0; i < resultCount; ++i) {
    BLEAdvertisedDevice device = results->getDevice(i);
    int rssi = device.getRSSI();
    if (rssi < GRIDRUNNER_BLE_IGNORE_RSSI_BELOW) {
      ignored++;
      continue;
    }
    if (rssi > peak) {
      peak = rssi;
    }
    if (device.haveName()) {
      known++;
    } else {
      unknown++;
    }
    if (bleSuggestsDrone(device)) {
      recordDroneCandidate(rssi, false);
    }
  }

  bleKnownCount = known;
  bleUnknownCount = unknown;
  bleIgnoredCount = ignored;
  bleRssiPeak = peak == -127 ? 0 : peak;
  bleScanCount++;
  pendingTelemetryScans++;
  lastBleScanMs = millis();
  if (bleScan != nullptr) {
    bleScan->clearResults();
  }
  trackerStatus = mqtt.connected() ? "linked" : "local";
  bleScanInProgress = false;
  dirty = true;
}

void scanBle() {
  if (bleScan == nullptr) {
    return;
  }

  uint32_t now = millis();
  if (bleScanInProgress) {
    if (!bleScan->isScanning() && now - bleScanStartedMs >= GRIDRUNNER_BLE_SCAN_SECONDS * 1000UL) {
      finishBleScan(bleScan->getResults());
    }
    return;
  }

  if (wifiScanInProgress || (lastBleScanMs != 0 && now - lastBleScanMs < GRIDRUNNER_BLE_SCAN_INTERVAL_MS)) {
    return;
  }

  if (bleScan->start(GRIDRUNNER_BLE_SCAN_SECONDS, bleScanComplete, false)) {
    bleScanInProgress = true;
    bleScanStartedMs = now;
    trackerStatus = "ble-scan";
  } else {
    lastBleScanMs = now;
    trackerStatus = "ble-scan-fail";
  }
  dirty = true;
}

void bleScanComplete(BLEScanResults results) {
  (void)results;
}

void publishTelemetry() {
  if (WiFi.status() != WL_CONNECTED || !mqtt.connected()) {
    return;
  }

  uint32_t now = millis();
  if (lastTelemetryMs != 0 && now - lastTelemetryMs < GRIDRUNNER_TELEMETRY_INTERVAL_MS) {
    return;
  }
  lastTelemetryMs = now;

  JsonDocument doc;
  doc["schema"] = "gridrunner.edge_node.v1";
  doc["node_id"] = GRIDRUNNER_NODE_ID;
  doc["profile"] = GRIDRUNNER_TRACKER_PROFILE;
  doc["timestamp"] = "1970-01-01T00:00:00Z";
  doc["uptime_seconds"] = millis() / 1000;
  doc["battery"]["percent"] = 0;
  doc["battery"]["voltage"] = 0;
  doc["battery"]["charging"] = false;
  doc["link"]["transport"] = "mqtt";
  doc["link"]["rssi"] = WiFi.RSSI();
  doc["link"]["last_sync_seconds"] = lastTelemetryOkMs == 0 ? 0 : (now - lastTelemetryOkMs) / 1000;
  doc["link"]["pending_scan_count"] = pendingTelemetryScans;
  doc["ble"]["window_seconds"] = GRIDRUNNER_BLE_SCAN_INTERVAL_MS / 1000;
  doc["ble"]["known_count"] = bleKnownCount;
  doc["ble"]["unknown_count"] = bleUnknownCount;
  doc["ble"]["ignored_count"] = bleIgnoredCount;
  doc["ble"]["rssi_peak"] = bleRssiPeak;
  doc["ble"]["scan_count"] = bleScanCount;
  doc["wifi"]["window_seconds"] = GRIDRUNNER_WIFI_SCAN_INTERVAL_MS / 1000;
  doc["wifi"]["ap_count"] = totalAps;
  doc["wifi"]["stored_count"] = apCount;
  doc["wifi"]["strongest_rssi"] = strongestRssi;
  doc["wifi"]["strongest_ssid"] = strongestSsid;
  doc["wifi"]["scan_count"] = scanCount;
  doc["drone"]["candidate_count"] = droneCandidateCount;
  doc["drone"]["wifi_count"] = droneWifiCount;
  doc["drone"]["ble_count"] = droneBleCount;
  doc["drone"]["rssi_peak"] = droneRssiPeak;

  JsonArray rows = doc["wifi"]["aps"].to<JsonArray>();
  for (size_t i = 0; i < apCount && i < 5; ++i) {
    JsonObject row = rows.add<JsonObject>();
    row["ssid"] = accessPoints[i].ssid;
    row["rssi"] = accessPoints[i].rssi;
    row["channel"] = accessPoints[i].channel;
    row["security"] = encryptionText(accessPoints[i].encryption);
    row["drone_candidate"] = accessPoints[i].droneCandidate;
  }

  String payload;
  serializeJson(doc, payload);
  if (mqtt.publish(mqttTopic().c_str(), payload.c_str(), true)) {
    lastTelemetryOkMs = now;
    pendingTelemetryScans = 0;
    trackerStatus = "pub";
  } else {
    trackerStatus = "pubfail";
  }
  dirty = true;
}

void apPoint(const AccessPoint &item, int index, int16_t &x, int16_t &y) {
  double angle = ((item.channel > 0 ? item.channel * 27 : index * 31) + index * 17) * DEG_TO_RAD;
  int strength = constrain(item.rssi, -95, -30);
  double radius = map(strength, -30, -95, 16, RADAR_R - 6);
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

void drawApBlips() {
  for (size_t i = 0; i < apCount; ++i) {
    int16_t x = 0;
    int16_t y = 0;
    apPoint(accessPoints[i], i, x, y);
    uint16_t color = accessPoints[i].droneCandidate ? COLOR_BAD : (accessPoints[i].rssi > -55 ? COLOR_HOT : COLOR_TEXT);
    if (i == selectedAp) {
      color = accessPoints[i].droneCandidate ? COLOR_BAD : COLOR_WARN;
    }
    gfx->fillCircle(x, y, i == selectedAp ? 4 : 3, color);
    gfx->drawPixel(x - 5, y, color);
    gfx->drawPixel(x + 5, y, color);
    gfx->drawPixel(x, y - 5, color);
    gfx->drawPixel(x, y + 5, color);
  }
}

void drawStatus() {
  size_t page = apCount == 0 ? 1 : selectedAp / AP_ROWS_PER_PAGE + 1;
  size_t pages = apCount == 0 ? 1 : (apCount + AP_ROWS_PER_PAGE - 1) / AP_ROWS_PER_PAGE;
  String signalStatus = "AP" + String(totalAps);
  signalStatus += " BL" + String(bleKnownCount + bleUnknownCount);
  signalStatus += " D" + String(droneCandidateCount);
  signalStatus += " R" + String(strongestRssi);

  String linkStatus = mqtt.connected() ? "UP" : "LOCAL";
  linkStatus += " B" + String(BRIGHTNESS_LEVELS[brightnessIndex]);
  linkStatus += viewMode == ViewMode::Detail ? " D" : " L";
  if (pages > 1) {
    linkStatus += " P" + String(page) + "/" + String(pages);
  }

  uint16_t color = mqtt.connected() ? COLOR_TEXT : COLOR_WARN;
  if (scanBusy()) {
    color = COLOR_WARN;
  }
  drawText(4, 296, signalStatus, color);
  drawText(4, 308, linkStatus, color);
}

void drawApList() {
  int y = 168;
  drawText(6, y, "SSID       RSSI CH SEC", COLOR_TEXT);
  y += 14;

  size_t pageStart = selectedAp / AP_ROWS_PER_PAGE * AP_ROWS_PER_PAGE;
  for (size_t rowIndex = 0; rowIndex < AP_ROWS_PER_PAGE; ++rowIndex) {
    size_t i = pageStart + rowIndex;
    if (i >= apCount) {
      drawText(6, y, "--         ---  -- ---", COLOR_DIM);
      y += 22;
      continue;
    }

    const AccessPoint &item = accessPoints[i];
    String ssid = item.ssid;
    if (ssid.length() > 9) {
      ssid = ssid.substring(0, 9);
    }
    while (ssid.length() < 9) {
      ssid += " ";
    }

    String row = ssid + " " + String(item.rssi);
    while (row.length() < 15) {
      row += " ";
    }
    row += String(item.channel);
    while (row.length() < 18) {
      row += " ";
    }
    row += item.droneCandidate ? "DRN" : encryptionText(item.encryption);

    uint16_t color = item.droneCandidate ? COLOR_BAD : (item.rssi > -55 ? COLOR_WARN : COLOR_TEXT);
    if (i == selectedAp && !item.droneCandidate) {
      color = COLOR_HOT;
    }
    drawText(6, y, row, color);
    y += 22;
  }
}

void drawApDetail() {
  if (apCount == 0) {
    drawText(16, 172, "NO SIGNALS", COLOR_WARN, 2);
    drawText(20, 204, "SCANNING WIFI", COLOR_DIM);
    return;
  }

  const AccessPoint &item = accessPoints[selectedAp];
  int y = 166;
  drawTextClipped(6, y, item.ssid, 12, COLOR_HOT, 2);
  y += 30;
  drawText(6, y, "RSSI " + String(item.rssi) + " DBM", COLOR_TEXT);
  y += 18;
  drawText(6, y, "CH " + String(item.channel), COLOR_TEXT);
  y += 18;
  drawText(6, y, "SEC " + encryptionText(item.encryption), COLOR_TEXT);
  y += 18;
  drawText(6, y, item.hidden ? "HIDDEN SSID" : "VISIBLE SSID", COLOR_DIM);
  y += 18;
  drawText(6, y, "SCAN " + String(scanCount), COLOR_DIM);
  y += 18;
  drawText(6, y, "BLE " + String(bleKnownCount + bleUnknownCount) + " PK " + String(bleRssiPeak), COLOR_DIM);
  y += 18;
  drawText(6, y, "DRN " + String(droneCandidateCount) + " PK " + String(droneRssiPeak), item.droneCandidate ? COLOR_BAD : COLOR_DIM);
}

void drawFrame() {
  gfx->fillScreen(COLOR_BG);
  drawStatus();

  drawRadarGrid();
  drawApBlips();
  if (apCount == 0) {
    drawText(18, 172, "LOCAL SCAN", COLOR_WARN, 2);
    drawText(18, 202, "AP 0 BLE " + String(bleKnownCount + bleUnknownCount), COLOR_DIM);
    drawText(18, 220, "DRN " + String(droneCandidateCount), droneCandidateCount > 0 ? COLOR_BAD : COLOR_DIM);
    drawText(18, 238, trackerStatus, mqtt.connected() ? COLOR_TEXT : COLOR_WARN);
  } else if (viewMode == ViewMode::Detail) {
    drawApDetail();
  } else {
    drawApList();
  }

  gfx->flush();
  dirty = false;
  lastFrameMs = millis();
}

void selectNextAp() {
  if (apCount == 0) {
    return;
  }
  selectedAp = (selectedAp + 1) % apCount;
  dirty = true;
}

void enterDetail() {
  if (apCount == 0) {
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
    selectNextAp();
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

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  BLEDevice::init("");
  bleScan = BLEDevice::getScan();
  bleScan->setActiveScan(false);
  bleScan->setInterval(160);
  bleScan->setWindow(80);

  mqtt.setServer(GRIDRUNNER_MQTT_HOST, GRIDRUNNER_MQTT_PORT);
  mqtt.setBufferSize(8192);
  mqtt.setKeepAlive(30);
}

void loop() {
  pollButton();
  connectWifi();
  connectMqtt();
  mqtt.loop();
  scanWifi();
  scanBle();
  publishTelemetry();

  if (millis() - lastFrameMs >= STATUS_REFRESH_MS) {
    dirty = true;
  }
  if (millis() - lastSweepMs >= SWEEP_REFRESH_MS) {
    lastSweepMs = millis();
    sweepDeg = (sweepDeg + 6) % 360;
    dirty = true;
  }
  if (dirty) {
    drawFrame();
  }
}
