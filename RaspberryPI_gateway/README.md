# Raspberry Pi LoRa TDMA Gateway

Python-based Single-Channel LoRa TDMA Gateway for Raspberry Pi, powered by **`radiogem`** (RadioLib C++ bindings).

This gateway is a 1-to-1 conversion of the ESP32-S3 gateway (`esp32_gateway`), preserving:
- Binary packet compatibility with existing sensor nodes (same byte alignment, packed structs, and header checksums).
- Gateway-coordinated TDMA superframe timing (periodic `SYNC` beacon broadcast followed by node time-slots).
- The exact same web dashboard interface and real-time visualization (`/` and `/api/nodes`).
- Support for hardware activity LED, buzzer alerts, and optional I2C SSD1306 OLED display.

---

## 1. Architecture

```text
       ┌─────────────────────────────────────────────────────────┐
       │              LoRa Sensor Nodes (ESP32-S3)               │
       │  Node 1 (Slot 1)                  Node 2 (Slot 2)       │
       └──────────────┬───────────────────────────┬──────────────┘
                      ▲                           ▲
                      │  SYNC Broadcast           │
                      │  DATA Packets             │
                      ▼                           ▼
       ┌─────────────────────────────────────────────────────────┐
       │             SX1262 LoRa Transceiver Module              │
       └──────────────────────────┬──────────────────────────────┘
                                  │ SPI / GPIO (CE1, NSS, DIO1, RST, BUSY)
                                  ▼
       ┌─────────────────────────────────────────────────────────┐
       │               Raspberry Pi 4 / 5 / Zero 2 W             │
       │                                                         │
       │  ┌───────────────────────────────────────────────────┐  │
       │  │               radiogem (pybind11)                 │  │
       │  │   RadioLib C++ Core + Linux lgpio hardware HAL    │  │
       │  └───────────────────────┬───────────────────────────┘  │
       │                          │                              │
       │  ┌───────────────────────▼───────────────────────────┐  │
       │  │               gateway.py (Python)                 │  │
       │  │  - TDMA Superframe Timer (2500ms SYNC cycle)      │  │
       │  │  - Non-blocking DIO1 Interrupt packet receiver    │  │
       │  │  - Node status, sequence & packet loss tracker    │  │
       │  │  - Optional LED, Buzzer & SSD1306 OLED            │  │
       │  └───────────────────────┬───────────────────────────┘  │
       │                          │                              │
       │  ┌───────────────────────▼───────────────────────────┐  │
       │  │             web_server.py (Threading)             │  │
       │  │  - GET /          -> dashboard.html (Live UI)     │  │
       │  │  - GET /api/nodes -> Real-time JSON telemetry     │  │
       │  └───────────────────────────────────────────────────┘  │
       └─────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

```text
RaspberryPI_gateway/
├── config.py             # Hardware pins, RF parameters, TDMA timers, and ports
├── protocol.py           # Struct definitions (PacketHeader, SyncPacket, DataPacket)
├── gateway.py            # TDMA superframe logic, packet processing, and state manager
├── peripherals.py        # LED indicator, buzzer alert, and optional SSD1306 display
├── web_server.py         # Threaded HTTP server serving dashboard and /api/nodes
├── dashboard.html        # Embedded interactive web dashboard (graphs, gauges, alerts)
├── main.py               # CLI entry point with configurable command-line arguments
├── test_gateway.py       # Unit tests for protocol binary pack/unpack verification
├── test_e2e_simulation.py# In-memory end-to-end integration test
└── README.md             # This guide
```

---

## 3. Hardware Connections (Raspberry Pi 40-Pin Header)

### SX1262 LoRa Radio (SPI0 CE1)

| SX1262 Pin | Raspberry Pi Pin | RPi Function | Default `config.py` Pin |
|---|---|---|---|
| **VCC** | Pin 1 or Pin 17 | 3.3V Power | 3.3V |
| **GND** | Pin 6, 9, 14, 20, or 25 | Ground | GND |
| **SCK** | Pin 23 | GPIO 11 (SPI0 SCLK) | Hardware SPI0 |
| **MISO** | Pin 21 | GPIO 9 (SPI0 MISO) | Hardware SPI0 |
| **MOSI** | Pin 19 | GPIO 10 (SPI0 MOSI) | Hardware SPI0 |
| **NSS / CS** | Pin 26 | GPIO 7 (SPI0 CE1) | `PIN_NSS = 7` (SPI ch 1) |
| **DIO1** | Pin 13 | GPIO 27 | `PIN_DIO1 = 27` |
| **RESET** | Pin 15 | GPIO 22 | `PIN_RST = 22` |
| **BUSY** | Pin 18 | GPIO 24 | `PIN_BUSY = 24` |

*(Note: If your SX1262 is wired to CE0 instead of CE1, use `--spi-ch 0 --nss 8` or change `SPI_CHANNEL = 0`, `PIN_NSS = 8` in `config.py`).*

### Optional Peripherals

| Peripheral | RPi Pin | Function | Config Parameter |
|---|---|---|---|
| **Status LED** | Pin 11 | GPIO 17 (via 330Ω resistor to GND) | `GATEWAY_LED_PIN = 17` |
| **Active Buzzer** | Pin 37 | GPIO 26 (High = Beep) | `BUZZER_PIN = 26` |
| **OLED SDA** | Pin 3 | GPIO 2 (I2C-1 SDA) | `ENABLE_OLED = True` |
| **OLED SCL** | Pin 5 | GPIO 3 (I2C-1 SCL) | `ENABLE_OLED = True` |

---

## 4. Installation & Requirements

On Raspberry Pi OS:

```bash
# 1. Install system prerequisites
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip liblgpio-dev cmake g++

# 2. Enable SPI and I2C in raspi-config if not already enabled:
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0

# 3. Install radiogem (from the project root)
cd /path/to/radiogem
pip install .

# 4. (Optional) Install gpiozero and PIL for LED/Buzzer/OLED support
pip install gpiozero luma.oled pillow
```

---

## 5. Running the Gateway

### Run with hardware (default settings):
```bash
python3 RaspberryPI_gateway/main.py
```

### Run with custom parameters:
```bash
python3 RaspberryPI_gateway/main.py --port 8080 --freq 866.5 --sf 7 --bw 125.0 --power 14
```

### Run in Simulation Mode (without SX1262 hardware attached):
```bash
python3 RaspberryPI_gateway/main.py --simulate
```

### Accessing the Web Dashboard:
Open your browser and navigate to:
```text
http://<raspberry-pi-ip>:8080/
```
The dashboard updates every 2 seconds via `/api/nodes` and shows live status, packet reception count, packet loss, accelerometer charts, temperature, gas levels, and active emergency alerts.

---

## 6. Running as a Systemd Service (Auto-Start on Boot)

To run the gateway continuously in the background on Raspberry Pi:

Create `/etc/systemd/system/lora-gateway.service`:
```ini
[Unit]
Description=LoRa TDMA Raspberry Pi Gateway
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/radiogem/RaspberryPI_gateway
ExecStart=/usr/bin/python3 /home/pi/radiogem/RaspberryPI_gateway/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable lora-gateway
sudo systemctl start lora-gateway
sudo systemctl status lora-gateway
```

