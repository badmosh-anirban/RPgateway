"""
Unit tests for Raspberry Pi Gateway protocol packing, unpacking, and JSON serialization.
"""

import json
import unittest
from protocol import (
    PROTOCOL_VERSION,
    PKT_SYNC,
    PKT_DATA,
    HEADER_SIZE,
    SYNC_PAYLOAD_SIZE,
    SENSOR_PAYLOAD_SIZE,
    SYNC_PACKET_SIZE,
    DATA_PACKET_SIZE,
    PacketHeader,
    SyncPayload,
    SensorPayload,
    SyncPacket,
    DataPacket,
)


class TestGatewayProtocol(unittest.TestCase):
    def test_packet_sizes(self):
        self.assertEqual(HEADER_SIZE, 12)
        self.assertEqual(SYNC_PAYLOAD_SIZE, 5)
        self.assertEqual(SENSOR_PAYLOAD_SIZE, 20)
        self.assertEqual(SYNC_PACKET_SIZE, 17)
        self.assertEqual(DATA_PACKET_SIZE, 32)

    def test_sync_packet_pack_unpack(self):
        sync = SyncPacket.create(
            frame_number=42,
            gateway_id=0,
            node_count=2,
            slot_duration_ms=1000,
            guard_time_ms=300,
        )
        packed = sync.pack()
        self.assertEqual(len(packed), 17)

        # Unpack header
        hdr = PacketHeader.unpack(packed[:12])
        self.assertEqual(hdr.version, PROTOCOL_VERSION)
        self.assertEqual(hdr.type, PKT_SYNC)
        self.assertEqual(hdr.node_id, 0)
        self.assertEqual(hdr.gateway_id, 0)
        self.assertEqual(hdr.frame_number, 42)
        self.assertEqual(hdr.payload_length, 5)

        # Unpack payload
        payload = SyncPayload.unpack(packed, 12)
        self.assertEqual(payload.slot_duration_ms, 1000)
        self.assertEqual(payload.guard_time_ms, 300)
        self.assertEqual(payload.node_count, 2)

    def test_data_packet_pack_unpack(self):
        hdr = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_DATA,
            node_id=1,
            gateway_id=0,
            sequence=10,
            frame_number=42,
            payload_length=SENSOR_PAYLOAD_SIZE,
        )
        sensor = SensorPayload(
            temperature_x10=265,  # 26.5 °C
            pressure_pa=101325,   # 1013.25 hPa
            gas_adc=650,
            flame=0,
            vibration=1,
            accel_x=12,           # 0.12 g
            accel_y=3,            # 0.03 g
            accel_z=98,           # 0.98 g
            uptime_seconds=3600,
        )
        raw_bytes = hdr.pack() + sensor.pack()
        self.assertEqual(len(raw_bytes), 32)

        data_pkt = DataPacket.unpack(raw_bytes)
        self.assertTrue(data_pkt.is_valid(expected_gateway_id=0, max_nodes=2))
        self.assertEqual(data_pkt.header.node_id, 1)
        self.assertEqual(data_pkt.header.sequence, 10)
        self.assertEqual(data_pkt.header.frame_number, 42)
        self.assertAlmostEqual(data_pkt.payload.temperature_celsius, 26.5)
        self.assertAlmostEqual(data_pkt.payload.pressure_hpa, 1013.25)
        self.assertEqual(data_pkt.payload.gas_adc, 650)
        self.assertEqual(data_pkt.payload.flame, 0)
        self.assertEqual(data_pkt.payload.vibration, 1)
        self.assertAlmostEqual(data_pkt.payload.accel_x_g, 0.12)
        self.assertAlmostEqual(data_pkt.payload.accel_y_g, 0.03)
        self.assertAlmostEqual(data_pkt.payload.accel_z_g, 0.98)
        self.assertEqual(data_pkt.payload.uptime_seconds, 3600)

    def test_negative_temperature_and_accel(self):
        hdr = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_DATA,
            node_id=2,
            gateway_id=0,
            sequence=1,
            frame_number=1,
            payload_length=SENSOR_PAYLOAD_SIZE,
        )
        sensor = SensorPayload(
            temperature_x10=-154,  # -15.4 °C
            pressure_pa=98500,
            gas_adc=200,
            flame=1,
            vibration=0,
            accel_x=-50,           # -0.50 g
            accel_y=-25,           # -0.25 g
            accel_z=100,           # 1.00 g
            uptime_seconds=50,
        )
        raw_bytes = hdr.pack() + sensor.pack()
        data_pkt = DataPacket.unpack(raw_bytes)
        self.assertAlmostEqual(data_pkt.payload.temperature_celsius, -15.4)
        self.assertAlmostEqual(data_pkt.payload.accel_x_g, -0.50)
        self.assertAlmostEqual(data_pkt.payload.accel_y_g, -0.25)


if __name__ == "__main__":
    unittest.main()

