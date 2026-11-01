"""
LoRa TDMA Protocol definition for Raspberry Pi Gateway.
Matches the binary packet layout of the ESP32-S3 sensor nodes.
"""

from dataclasses import dataclass
import struct
from typing import Optional, Tuple

PROTOCOL_VERSION = 1

# Packet Types
PKT_SYNC = 1
PKT_DATA = 2

# Struct format strings (little-endian, packed):
# PacketHeader:
#   uint8_t version
#   uint8_t type
#   uint8_t nodeId
#   uint8_t gatewayId
#   uint16_t sequence
#   uint32_t frameNumber
#   uint16_t payloadLength
HEADER_FORMAT = "<BBBBHIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 12 bytes

# SyncPayload:
#   uint16_t slotDurationMs
#   uint16_t guardTimeMs
#   uint8_t nodeCount
SYNC_PAYLOAD_FORMAT = "<HHB"
SYNC_PAYLOAD_SIZE = struct.calcsize(SYNC_PAYLOAD_FORMAT)  # 5 bytes

# SensorPayload:
#   int16_t temperatureX10
#   uint32_t pressurePa
#   uint16_t gasAdc
#   uint8_t flame
#   uint8_t vibration
#   int16_t accelX
#   int16_t accelY
#   int16_t accelZ
#   uint32_t uptimeSeconds
SENSOR_PAYLOAD_FORMAT = "<hIHBBhhhI"
SENSOR_PAYLOAD_SIZE = struct.calcsize(SENSOR_PAYLOAD_FORMAT)  # 20 bytes

# Combined Packets
SYNC_PACKET_FORMAT = HEADER_FORMAT + SYNC_PAYLOAD_FORMAT[1:]
SYNC_PACKET_SIZE = HEADER_SIZE + SYNC_PAYLOAD_SIZE  # 17 bytes

DATA_PACKET_FORMAT = HEADER_FORMAT + SENSOR_PAYLOAD_FORMAT[1:]
DATA_PACKET_SIZE = HEADER_SIZE + SENSOR_PAYLOAD_SIZE  # 32 bytes


@dataclass
class PacketHeader:
    version: int = PROTOCOL_VERSION
    type: int = PKT_SYNC
    node_id: int = 0
    gateway_id: int = 0
    sequence: int = 0
    frame_number: int = 0
    payload_length: int = 0

    def pack(self) -> bytes:
        return struct.pack(
            HEADER_FORMAT,
            self.version,
            self.type,
            self.node_id,
            self.gateway_id,
            self.sequence,
            self.frame_number,
            self.payload_length,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "PacketHeader":
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data length ({len(data)}) < HEADER_SIZE ({HEADER_SIZE})")
        (
            version,
            pkt_type,
            node_id,
            gateway_id,
            sequence,
            frame_number,
            payload_length,
        ) = struct.unpack_from(HEADER_FORMAT, data)
        return cls(
            version=version,
            type=pkt_type,
            node_id=node_id,
            gateway_id=gateway_id,
            sequence=sequence,
            frame_number=frame_number,
            payload_length=payload_length,
        )


@dataclass
class SyncPayload:
    slot_duration_ms: int = 1000
    guard_time_ms: int = 300
    node_count: int = 2

    def pack(self) -> bytes:
        return struct.pack(
            SYNC_PAYLOAD_FORMAT,
            self.slot_duration_ms,
            self.guard_time_ms,
            self.node_count,
        )

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> "SyncPayload":
        slot_duration_ms, guard_time_ms, node_count = struct.unpack_from(
            SYNC_PAYLOAD_FORMAT, data, offset
        )
        return cls(
            slot_duration_ms=slot_duration_ms,
            guard_time_ms=guard_time_ms,
            node_count=node_count,
        )


@dataclass
class SensorPayload:
    temperature_x10: int = -32768  # INT16_MIN represents unavailable
    pressure_pa: int = 0
    gas_adc: int = 0
    flame: int = 0
    vibration: int = 0
    accel_x: int = 0  # 100 * g
    accel_y: int = 0
    accel_z: int = 0
    uptime_seconds: int = 0

    @property
    def temperature_celsius(self) -> Optional[float]:
        if self.temperature_x10 == -32768:
            return None
        return self.temperature_x10 / 10.0

    @property
    def pressure_hpa(self) -> float:
        return self.pressure_pa / 100.0

    @property
    def accel_x_g(self) -> float:
        return self.accel_x / 100.0

    @property
    def accel_y_g(self) -> float:
        return self.accel_y / 100.0

    @property
    def accel_z_g(self) -> float:
        return self.accel_z / 100.0

    def pack(self) -> bytes:
        return struct.pack(
            SENSOR_PAYLOAD_FORMAT,
            self.temperature_x10,
            self.pressure_pa,
            self.gas_adc,
            1 if self.flame else 0,
            1 if self.vibration else 0,
            self.accel_x,
            self.accel_y,
            self.accel_z,
            self.uptime_seconds,
        )

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> "SensorPayload":
        (
            temp_x10,
            pressure,
            gas,
            flame,
            vibration,
            ax,
            ay,
            az,
            uptime,
        ) = struct.unpack_from(SENSOR_PAYLOAD_FORMAT, data, offset)
        return cls(
            temperature_x10=temp_x10,
            pressure_pa=pressure,
            gas_adc=gas,
            flame=flame,
            vibration=vibration,
            accel_x=ax,
            accel_y=ay,
            accel_z=az,
            uptime_seconds=uptime,
        )


@dataclass
class SyncPacket:
    header: PacketHeader
    payload: SyncPayload

    @classmethod
    def create(
        cls,
        frame_number: int,
        gateway_id: int = 0,
        node_count: int = 2,
        slot_duration_ms: int = 1000,
        guard_time_ms: int = 300,
    ) -> "SyncPacket":
        payload = SyncPayload(
            slot_duration_ms=slot_duration_ms,
            guard_time_ms=guard_time_ms,
            node_count=node_count,
        )
        header = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_SYNC,
            node_id=0,
            gateway_id=gateway_id,
            sequence=0,
            frame_number=frame_number,
            payload_length=SYNC_PAYLOAD_SIZE,
        )
        return cls(header=header, payload=payload)

    def pack(self) -> bytes:
        return self.header.pack() + self.payload.pack()


@dataclass
class DataPacket:
    header: PacketHeader
    payload: SensorPayload

    @classmethod
    def unpack(cls, data: bytes) -> "DataPacket":
        if len(data) != DATA_PACKET_SIZE:
            raise ValueError(
                f"DataPacket size mismatch: expected {DATA_PACKET_SIZE}, got {len(data)}"
            )
        header = PacketHeader.unpack(data[:HEADER_SIZE])
        payload = SensorPayload.unpack(data, HEADER_SIZE)
        return cls(header=header, payload=payload)

    def is_valid(self, expected_gateway_id: int = 0, max_nodes: int = 2) -> bool:
        return (
            self.header.version == PROTOCOL_VERSION
            and self.header.type == PKT_DATA
            and self.header.gateway_id == expected_gateway_id
            and 1 <= self.header.node_id <= max_nodes
            and self.header.payload_length == SENSOR_PAYLOAD_SIZE
        )

