// v1.0.0: before porting to pi
// v1.0.1: start of porting

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <WebServer.h>
#include <WiFi.h>
#include <Wire.h>

#include "config.h"
#include "dashboard.h"
#include "protocol.h"

bool gatewayLedBlinking = false;
uint32_t gatewayLedOffAt = 0;

const uint32_t GATEWAY_LED_BLINK_MS = 100;

Module radioModule(LORA_NSS, LORA_DIO1, LORA_RST, LORA_BUSY);
SX1262 radio(&radioModule);
WebServer server(80);
Adafruit_SSD1306 display(128, 64, &Wire, -1);

struct NodeStatus {
  uint8_t nodeId;
  bool online;
  bool seen;
  uint16_t lastSequence;
  uint32_t lastFrame;
  uint32_t lastSeen;
  uint32_t packetsReceived;
  uint32_t packetsMissed;
  SensorPayload sensor;
  int16_t rssi;
  float snr;
};

NodeStatus nodes[NODE_COUNT]{};
uint32_t frameNumber = 0;
uint32_t lastSyncAt = 0;
uint32_t syncMessagesSent = 0;
uint32_t syncMessagesFailed = 0;
uint32_t lastDisplayUpdate = 0;
uint32_t buzzerOffAt = 0;
bool displayAvailable = false;

void blinkGatewayLed() {
  digitalWrite(GATEWAY_LED, HIGH);
  gatewayLedBlinking = true;
  gatewayLedOffAt = millis() + GATEWAY_LED_BLINK_MS;
}

void updateGatewayLed() {
  if (gatewayLedBlinking &&
      static_cast<int32_t>(millis() - gatewayLedOffAt) >= 0) {

    digitalWrite(GATEWAY_LED, LOW);
    gatewayLedBlinking = false;
  }
}

void triggerBuzzer() {
  digitalWrite(BUZZER_PIN, HIGH);
  buzzerOffAt = millis() + BUZZER_ON_TIME_MS;
}

void updateBuzzer() {
  if (buzzerOffAt != 0 && static_cast<int32_t>(millis() - buzzerOffAt) >= 0) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerOffAt = 0;
  }
}

void initializeDisplay() {
  Wire.begin(OLED_SDA, OLED_SCL);
  displayAvailable = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  if (!displayAvailable) {
    Serial.println("OLED initialization failed; continuing without display.");
    return;
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("Mine Gateway");
  display.println("Starting...");
  display.display();
}

void printNodeStatus(uint8_t index) {
  const NodeStatus &node = nodes[index];
  display.println();
  display.print("N");
  display.print(node.nodeId);
  display.print(node.online ? ": ON " : ": OFF ");
  display.print("P:");
  display.print(node.packetsReceived);
  display.print(" M:");
  display.println(node.packetsMissed);

  if (node.seen) {
    display.print(" R:");
    display.print(node.rssi);
    display.print(" | S:");
    display.println(node.snr, 1);
  } else {
    display.println(" R:-- S:--");
  }
}

void updateDisplay() {
  if (!displayAvailable ||
      millis() - lastDisplayUpdate < DISPLAY_UPDATE_INTERVAL_MS) {
    return;
  }
  lastDisplayUpdate = millis();

  display.clearDisplay();
  display.setCursor(0, 0);
  display.print("SYNC:");
  display.print(syncMessagesSent);
  display.print(" | F:");
  display.println(frameNumber);
  printNodeStatus(0);
  if (NODE_COUNT > 1) {
    printNodeStatus(1);
  }
  // display.print("WiFi:");
  // display.println(WiFi.status() == WL_CONNECTED ? "ON" : "OFF");
  //  display.print("B:");
  //  display.print(syncMessagesFailed);
  //  display.print(" ");
  //  display.println(buzzerOffAt != 0 ? "ALERT" : "OK");
  display.display();
}

String jsonEscape(const String &value) {
  String escaped = value;
  escaped.replace("\\", "\\\\");
  escaped.replace("\"", "\\\"");
  return escaped;
}

String formatLastSeen(const NodeStatus &node) {
  if (!node.seen) {
    return "never";
  }
  return String((millis() - node.lastSeen) / 1000UL) + "s ago";
}

// String accelerationText(const SensorPayload &sensor) {
//     return String(sensor.accelX / 100.0f, 2) + ", " +
//            String(sensor.accelY / 100.0f, 2) + ", " +
//            String(sensor.accelZ / 100.0f, 2);
// }

void sendJsonResponse() {
  String json = "[";
  for (uint8_t index = 0; index < NODE_COUNT; ++index) {
    const NodeStatus &node = nodes[index];
    if (index > 0) {
      json += ",";
    }
    json += "{\"id\":" + String(node.nodeId);
    json += ",\"online\":" + String(node.online ? "true" : "false");
    json += ",\"temperature\":" + String(node.sensor.temperatureX10);
    json += ",\"pressure\":" + String(node.sensor.pressurePa);
    json += ",\"gas\":" + String(node.sensor.gasAdc);
    json += ",\"flame\":" + String(node.sensor.flame ? "true" : "false");
    json +=
        ",\"vibration\":" + String(node.sensor.vibration ? "true" : "false");
    // json += ",\"acceleration\":\"" +
    // jsonEscape(accelerationText(node.sensor)) + "\"";

    json += ",\"acceleration\":{";
    json += "\"x\":" + String(node.sensor.accelX / 100.0f, 2);
    json += ",\"y\":" + String(node.sensor.accelY / 100.0f, 2);
    json += ",\"z\":" + String(node.sensor.accelZ / 100.0f, 2);
    json += "}";

    json += ",\"packets\":" + String(node.packetsReceived);
    json += ",\"missed\":" + String(node.packetsMissed);
    json += ",\"rssi\":" + String(node.rssi);
    json += ",\"snr\":" + String(node.snr, 1);
    json += ",\"frame\":" + String(node.lastFrame);
    json += ",\"lastSeen\":\"" + jsonEscape(formatLastSeen(node)) + "\"}";
  }
  json += "]";
  server.send(200, "application/json", json);
}

void initializeNodeStatus() {
  for (uint8_t index = 0; index < NODE_COUNT; ++index) {
    nodes[index].nodeId = index + 1;
    nodes[index].sensor.temperatureX10 = INT16_MIN;
  }
}

void initializeRadio() {
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_NSS);
  pinMode(LORA_ANT_SW, OUTPUT);
  digitalWrite(LORA_ANT_SW, HIGH);

  int16_t state =
      radio.begin(LORA_FREQUENCY_MHZ, LORA_BANDWIDTH_KHZ, LORA_SPREADING_FACTOR,
                  LORA_CODING_RATE, LORA_SYNC_WORD, LORA_OUTPUT_POWER_DBM,
                  LORA_PREAMBLE_LENGTH);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.printf("Radio initialization failed: %d\n", state);
    while (true) {
      digitalWrite(GATEWAY_LED, !digitalRead(GATEWAY_LED));
      delay(250);
    }
  }
  radio.setCRC(true);
  radio.startReceive();
}

void sendSync() {
  SyncPacket packet{};
  // below 3 are for authentication
  packet.header.version = PROTOCOL_VERSION;
  packet.header.type = PKT_SYNC;
  packet.header.nodeId = 0; // not used
  packet.header.gatewayId = GATEWAY_ID;

  packet.header.sequence = 0;              // prolly not used too
  packet.header.frameNumber = frameNumber; // actually used by the node
  packet.header.payloadLength = sizeof(packet.payload); // prolly not used too

  // below 3 are unused
  packet.payload.slotDurationMs = SYNC_SLOT_DURATION_MS;
  packet.payload.guardTimeMs = SYNC_GUARD_TIME_MS;
  packet.payload.nodeCount = NODE_COUNT;

  int16_t state = radio.transmit(reinterpret_cast<const uint8_t *>(&packet),
                                 sizeof(packet));
  if (state == RADIOLIB_ERR_NONE) {
    ++syncMessagesSent;
    blinkGatewayLed();
  } else {
    ++syncMessagesFailed;
  }
  Serial.printf("SYNC frame %lu: %s\n", static_cast<unsigned long>(frameNumber),
                state == RADIOLIB_ERR_NONE ? "sent" : "failed");
  radio.startReceive();
}

void processDataPacket() {
  DataPacket packet{};
  if (radio.getPacketLength() != sizeof(packet)) {
    radio.startReceive();
    return;
  }

  int16_t state =
      radio.readData(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
  int16_t rssi = static_cast<int16_t>(radio.getRSSI());
  float snr = radio.getSNR();
  radio.startReceive();

  if (state != RADIOLIB_ERR_NONE || packet.header.version != PROTOCOL_VERSION ||
      packet.header.type != PKT_DATA || packet.header.gatewayId != GATEWAY_ID ||
      packet.header.nodeId < 1 || packet.header.nodeId > NODE_COUNT ||
      packet.header.payloadLength != sizeof(packet.payload)) {
    return;
  }

  NodeStatus &node = nodes[packet.header.nodeId - 1];
  bool newSensorAlert = (packet.payload.flame || packet.payload.vibration) &&
                        (!node.sensor.flame && !node.sensor.vibration);
  if (node.seen && packet.header.sequence > node.lastSequence + 1) {
    node.packetsMissed += packet.header.sequence - node.lastSequence - 1;
  }
  node.lastSequence = packet.header.sequence;
  node.lastFrame = packet.header.frameNumber;
  node.lastSeen = millis();
  node.seen = true;
  node.online = true;
  node.packetsReceived++;
  node.sensor = packet.payload;
  node.rssi = rssi;
  node.snr = snr;
  if (newSensorAlert) {
    triggerBuzzer();
  }

  Serial.printf("DATA node=%u frame=%lu seq=%u RSSI=%d SNR=%.1f\n", node.nodeId,
                static_cast<unsigned long>(node.lastFrame), node.lastSequence,
                node.rssi, node.snr);
}

void pollRadio() {
  if (digitalRead(LORA_DIO1) != HIGH) {
    return;
  }
  if (radio.getPacketLength() == sizeof(DataPacket)) {
    processDataPacket();
  } else {
    radio.startReceive();
  }
}

void updateNodeTimeouts() {
  uint32_t now = millis();
  for (uint8_t index = 0; index < NODE_COUNT; ++index) {
    if (nodes[index].seen && now - nodes[index].lastSeen > OFFLINE_TIMEOUT_MS) {
      if (nodes[index].online) {
        // triggerBuzzer();
      }
      nodes[index].online = false;
    }
  }
}

void initializeWebServer() {
  server.on("/", HTTP_GET,
            []() { server.send_P(200, "text/html", DASHBOARD_HTML); });
  server.on("/api/nodes", HTTP_GET, sendJsonResponse);
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  uint8_t attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts++ < 30) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Dashboard: http://");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Wi-Fi unavailable; LoRa will continue running.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(GATEWAY_LED, OUTPUT);
  pinMode(GATEWAY_BUTTON, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  initializeNodeStatus();
  initializeDisplay();
  initializeRadio();
  connectWiFi();
  initializeWebServer();

  frameNumber = 0;
  sendSync();
  lastSyncAt = millis();
}

void loop() {
  uint32_t now = millis();
  if (now - lastSyncAt >= SUPERFRAME_MS) {
    ++frameNumber;
    sendSync();
    lastSyncAt = now;
  }

  pollRadio();
  updateNodeTimeouts();
  updateBuzzer();
  updateGatewayLed();
  updateDisplay();
  server.handleClient();
  delay(2);
}