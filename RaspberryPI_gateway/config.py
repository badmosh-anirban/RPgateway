"""
Configuration parameters for Raspberry Pi LoRa TDMA Gateway.
"""

# Gateway Identity & Node Setup
GATEWAY_ID = 0
NODE_COUNT = 2

# TDMA Superframe & Timeout Parameters (in milliseconds)
SUPERFRAME_MS = 2500         # Duration of SYNC interval
OFFLINE_TIMEOUT_MS = 10000   # Mark node offline if no packet received within 10s
SYNC_SLOT_DURATION_MS = 1000 # Slot duration communicated to nodes
SYNC_GUARD_TIME_MS = 300     # Guard time between slots

# SX1262 LoRa Radio RF Parameters
LORA_FREQUENCY_MHZ = 866.5
LORA_BANDWIDTH_KHZ = 125.0
LORA_SPREADING_FACTOR = 7
LORA_CODING_RATE = 5
LORA_SYNC_WORD = 0x12
LORA_OUTPUT_POWER_DBM = 10
LORA_PREAMBLE_LENGTH = 8
LORA_CRC = True
LORA_TCXO_VOLTAGE = 1.6      # Set to 0.0 if using an external XTAL crystal module

# Raspberry Pi Hardware Connections (BCM GPIO pin numbering)
# Default SX1262 SPI & GPIO mapping for Raspberry Pi:
SPI_CHANNEL = 1              # SPI0 CE1 (Pin 26, GPIO 7)
SPI_SPEED_HZ = 2000000       # 2 MHz SPI clock
PIN_NSS = 7                  # Chip Select (NSS) -> GPIO 7
PIN_DIO1 = 27                # Radio DIO1 Interrupt -> GPIO 27
PIN_RST = 22                 # Radio Reset -> GPIO 22
PIN_BUSY = 24                # Radio Busy -> GPIO 24

# Optional Peripheral Indicators (BCM numbering, set to None if unused)
GATEWAY_LED_PIN = 17         # Activity indicator LED (e.g. GPIO 17)
GATEWAY_LED_BLINK_MS = 100   # LED on-duration per SYNC transmit

BUZZER_PIN = 26              # Active buzzer pin for alerts (e.g. GPIO 26)
BUZZER_ON_TIME_MS = 500      # Buzzer duration when alert triggers

# Optional SSD1306 128x64 I2C OLED Display
ENABLE_OLED = False          # Set to True if I2C SSD1306 is attached
OLED_I2C_PORT = 1            # /dev/i2c-1
OLED_ADDRESS = 0x3C
DISPLAY_UPDATE_INTERVAL_MS = 1000

# Web Dashboard Server
WEB_HOST = "0.0.0.0"         # Listen on all network interfaces
WEB_PORT = 8080              # Port 8080 (avoids requiring root permissions; can be set to 80)

