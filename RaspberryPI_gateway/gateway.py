"""
Main TDMA LoRa Gateway implementation for Raspberry Pi.
Coordinates TDMA superframes, SYNC beacons, node status tracking,
peripherals, and the web dashboard.
"""

from dataclasses import dataclass, field
import json
import logging
import signal
import sys
import threading
import time
from typing import List, Optional

import config
from protocol import (
    PROTOCOL_VERSION,
    PKT_DATA,
    DATA_PACKET_SIZE,
    DataPacket,
    SensorPayload,
    SyncPacket,
)
from peripherals import PeripheralsManager
from web_server import GatewayWebServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Gateway")

# Try to import radiogem
try:
    from radiogem import SX1262, ERR_NONE, get_status_text
    RADIOGEM_AVAILABLE = True
except ImportError:
    RADIOGEM_AVAILABLE = False
    SX1262 = None
    ERR_NONE = 0
    get_status_text = lambda st: f"Status {st}"


@dataclass
class NodeState:
    node_id: int
    online: bool = False
    seen: bool = False
    last_sequence: int = 0
    last_frame: int = 0
    last_seen: float = 0.0  # monotonic timestamp
    packets_received: int = 0
    packets_missed: int = 0
    sensor: SensorPayload = field(default_factory=SensorPayload)
    rssi: int = 0
    snr: float = 0.0


class Gateway:
    def __init__(self, simulate: bool = False):
        self.simulate = simulate or not RADIOGEM_AVAILABLE
        if not RADIOGEM_AVAILABLE and not simulate:
            logger.warning(
                "radiogem library not found! Running in simulated/dry-run mode. "
                "Install radiogem on Raspberry Pi to enable real RF hardware."
            )
            self.simulate = True

        self.running: bool = False
        self.lock = threading.Lock()

        # Gateway state
        self.frame_number: int = 0
        self.sync_messages_sent: int = 0
        self.sync_messages_failed: int = 0
        self.last_sync_at: float = 0.0

        # Initialize node tracking
        self.nodes: List[NodeState] = [
            NodeState(node_id=i + 1) for i in range(config.NODE_COUNT)
        ]

        # Peripherals & Web Server
        self.peripherals = PeripheralsManager()
        self.web_server = GatewayWebServer(
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            get_nodes_json_func=self.get_nodes_json,
        )

        # Radio instance
        self.radio = None
        self.received_flag: bool = False

    def init_radio(self):
        if self.simulate:
            logger.info("[Radio] Running in simulated mode (no SX1262 hardware attached).")
            return

        logger.info(
            f"[Radio] Initializing SX1262 on SPI ch={config.SPI_CHANNEL}, "
            f"NSS={config.PIN_NSS}, DIO1={config.PIN_DIO1}, RST={config.PIN_RST}, BUSY={config.PIN_BUSY}..."
        )

        self.radio = SX1262(
            spi_channel=config.SPI_CHANNEL,
            spi_speed=config.SPI_SPEED_HZ,
            nss=config.PIN_NSS,
            dio1=config.PIN_DIO1,
            reset=config.PIN_RST,
            busy=config.PIN_BUSY,
        )

        logger.info(
            f"[Radio] Configuring modem: {config.LORA_FREQUENCY_MHZ} MHz, "
            f"BW={config.LORA_BANDWIDTH_KHZ} kHz, SF={config.LORA_SPREADING_FACTOR}, "
            f"CR=4/{config.LORA_CODING_RATE}, Power={config.LORA_OUTPUT_POWER_DBM} dBm, "
            f"SyncWord=0x{config.LORA_SYNC_WORD:02X}"
        )

        status = self.radio.begin(
            frequency=config.LORA_FREQUENCY_MHZ,
            bandwidth=config.LORA_BANDWIDTH_KHZ,
            spreading_factor=config.LORA_SPREADING_FACTOR,
            coding_rate=config.LORA_CODING_RATE,
            sync_word=config.LORA_SYNC_WORD,
            power=config.LORA_OUTPUT_POWER_DBM,
            preamble_length=config.LORA_PREAMBLE_LENGTH,
            tcxo_voltage=config.LORA_TCXO_VOLTAGE,
        )

        if status != ERR_NONE:
            logger.error(f"[Radio] Initialization failed: {get_status_text(status)}")
            raise RuntimeError(f"SX1262 begin failed: {get_status_text(status)}")

        self.radio.set_crc(config.LORA_CRC)

        # Attach interrupt callback for non-blocking packet reception
        def on_packet_received():
            self.received_flag = True

        self.radio.set_packet_received_action(on_packet_received)

        # Put into continuous receive mode
        self.radio.start_receive()
        logger.info("[Radio] Modem successfully initialized and listening for packets.")

    def send_sync(self):
        sync_packet = SyncPacket.create(
            frame_number=self.frame_number,
            gateway_id=config.GATEWAY_ID,
            node_count=config.NODE_COUNT,
            slot_duration_ms=config.SYNC_SLOT_DURATION_MS,
            guard_time_ms=config.SYNC_GUARD_TIME_MS,
        )
        packet_bytes = sync_packet.pack()

        if self.simulate:
            self.sync_messages_sent += 1
            self.peripherals.blink_led()
            logger.info(f"SYNC frame {self.frame_number}: sent (simulated, {len(packet_bytes)} bytes)")
            return

        status = self.radio.transmit(packet_bytes)
        if status == ERR_NONE:
            self.sync_messages_sent += 1
            self.peripherals.blink_led()
            logger.info(f"SYNC frame {self.frame_number}: sent ({len(packet_bytes)} bytes)")
        else:
            self.sync_messages_failed += 1
            logger.warning(
                f"SYNC frame {self.frame_number}: failed ({get_status_text(status)})"
            )

        # Immediately return to continuous reception
        self.radio.start_receive()

    def poll_radio(self):
        if self.simulate or self.radio is None:
            return

        if self.received_flag or self.radio.has_received:
            self.received_flag = False

            # Read packet from SX1262
            packet = self.radio.read_data()

            # Immediately restart continuous receive mode for the next node slot
            self.radio.start_receive()

            if packet:
                self.process_packet(packet)
            else:
                logger.debug(f"Read packet returned None: {self.radio.get_status_text()}")

    def process_packet(self, packet):
        raw_data = packet.data
        if len(raw_data) != DATA_PACKET_SIZE:
            logger.debug(
                f"Ignored packet with unexpected size: {len(raw_data)} bytes "
                f"(expected {DATA_PACKET_SIZE})"
            )
            return

        try:
            data_pkt = DataPacket.unpack(raw_data)
        except Exception as e:
            logger.warning(f"Failed to decode data packet: {e}")
            return

        if not data_pkt.is_valid(
            expected_gateway_id=config.GATEWAY_ID, max_nodes=config.NODE_COUNT
        ):
            logger.debug(f"Packet validation failed: {data_pkt.header}")
            return

        node_index = data_pkt.header.node_id - 1
        with self.lock:
            node = self.nodes[node_index]
            new_alert = (
                (data_pkt.payload.flame or data_pkt.payload.vibration)
                and (not node.sensor.flame and not node.sensor.vibration)
            )

            # Detect packet loss
            if node.seen and data_pkt.header.sequence > node.last_sequence + 1:
                node.packets_missed += data_pkt.header.sequence - node.last_sequence - 1

            node.last_sequence = data_pkt.header.sequence
            node.last_frame = data_pkt.header.frame_number
            node.last_seen = time.monotonic()
            node.seen = True
            node.online = True
            node.packets_received += 1
            node.sensor = data_pkt.payload
            node.rssi = int(packet.rssi)
            node.snr = round(float(packet.snr), 1)

        if new_alert:
            self.peripherals.trigger_buzzer()

        temp_str = (
            f"{node.sensor.temperature_celsius:.1f}°C"
            if node.sensor.temperature_celsius is not None
            else "N/A"
        )
        logger.info(
            f"DATA node={node.node_id} frame={node.last_frame} seq={node.last_sequence} "
            f"RSSI={node.rssi} dBm SNR={node.snr:.1f} dB Temp={temp_str} "
            f"Press={node.sensor.pressure_hpa:.1f} hPa Gas={node.sensor.gas_adc} "
            f"Flame={node.sensor.flame} Vib={node.sensor.vibration}"
        )

    def update_node_timeouts(self):
        now = time.monotonic()
        timeout_sec = config.OFFLINE_TIMEOUT_MS / 1000.0

        with self.lock:
            for node in self.nodes:
                if node.seen and (now - node.last_seen) > timeout_sec:
                    if node.online:
                        logger.warning(f"Node {node.node_id} offline (timeout > {config.OFFLINE_TIMEOUT_MS}ms)")
                    node.online = False

    def get_nodes_json(self) -> str:
        now = time.monotonic()
        data = []
        with self.lock:
            for node in self.nodes:
                if not node.seen:
                    last_seen_str = "never"
                else:
                    elapsed_sec = int(now - node.last_seen)
                    last_seen_str = f"{elapsed_sec}s ago"

                node_dict = {
                    "id": node.node_id,
                    "online": node.online,
                    "temperature": node.sensor.temperature_x10,
                    "pressure": node.sensor.pressure_pa,
                    "gas": node.sensor.gas_adc,
                    "flame": bool(node.sensor.flame),
                    "vibration": bool(node.sensor.vibration),
                    "acceleration": {
                        "x": round(node.sensor.accel_x / 100.0, 2),
                        "y": round(node.sensor.accel_y / 100.0, 2),
                        "z": round(node.sensor.accel_z / 100.0, 2),
                    },
                    "packets": node.packets_received,
                    "missed": node.packets_missed,
                    "rssi": node.rssi,
                    "snr": round(node.snr, 1),
                    "frame": node.last_frame,
                    "lastSeen": last_seen_str,
                }
                data.append(node_dict)
        return json.dumps(data)

    def start(self):
        self.running = True
        logger.info("Starting LoRa TDMA Gateway...")

        self.init_radio()
        self.web_server.start()

        # Send initial frame 0 SYNC
        self.frame_number = 0
        self.send_sync()
        self.last_sync_at = time.monotonic()

        superframe_sec = config.SUPERFRAME_MS / 1000.0

        try:
            while self.running:
                now = time.monotonic()

                # TDMA superframe interval check
                if now - self.last_sync_at >= superframe_sec:
                    self.frame_number += 1
                    self.send_sync()
                    self.last_sync_at = now

                # Poll incoming packets
                self.poll_radio()

                # Check timeouts for online/offline status
                self.update_node_timeouts()

                # Update LED & Buzzer timers
                self.peripherals.update()

                # Update OLED display if enabled
                self.peripherals.update_display(
                    self.sync_messages_sent, self.frame_number, self.nodes
                )

                # Short sleep to prevent CPU starvation while maintaining sub-millisecond precision
                time.sleep(0.005)

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, stopping gateway...")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        logger.info("Shutting down Gateway...")

        self.web_server.stop()
        self.peripherals.close()

        if self.radio:
            try:
                self.radio.clear_packet_received_action()
                self.radio.close()
                logger.info("[Radio] SX1262 closed cleanly.")
            except Exception as e:
                logger.error(f"[Radio] Error closing radio: {e}")
            self.radio = None

        logger.info("Gateway stopped.")

