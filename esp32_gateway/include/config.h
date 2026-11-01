#pragma once

// Add your Wi-Fi credentials before flashing the gateway.
#define WIFI_SSID "My2GHz"
#define WIFI_PASSWORD "789hh23e21"

#define GATEWAY_ID 0
#define NODE_COUNT 2

// TDMA parameters
#define SUPERFRAME_MS 2500UL //change this to change duration of SYNC
#define OFFLINE_TIMEOUT_MS 10000UL

// SX1262 pins on the XIAO ESP32-S3 + SX1262 combo.
#define LORA_NSS 41
#define LORA_SCK 7
#define LORA_MOSI 9
#define LORA_MISO 8
#define LORA_RST 42
#define LORA_BUSY 40
#define LORA_DIO1 39
#define LORA_ANT_SW 38

#define GATEWAY_LED 48
#define GATEWAY_BUTTON 21

// 0.96 inch SSD1306 I2C display.
#define OLED_SDA 5
#define OLED_SCL 6
#define OLED_ADDRESS 0x3C
#define DISPLAY_UPDATE_INTERVAL_MS 1000UL


// Active buzzer: HIGH turns the buzzer on.
#define BUZZER_PIN 7
#define BUZZER_ON_TIME_MS 500UL


// radio parameters
#define LORA_FREQUENCY_MHZ 866.5
#define LORA_BANDWIDTH_KHZ 125.0
#define LORA_SPREADING_FACTOR 7
#define LORA_CODING_RATE 5
#define LORA_SYNC_WORD 0x12
#define LORA_OUTPUT_POWER_DBM 10
#define LORA_PREAMBLE_LENGTH 8

// unused by the nodes as of now
#define SYNC_SLOT_DURATION_MS 1000
#define SYNC_GUARD_TIME_MS 300

