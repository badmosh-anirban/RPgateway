"""
Unit test for Gateway state tracking, JSON output, and node transitions in simulation mode.
Runs fully in-memory without requiring network socket binding.
"""

import json
import os
import unittest
from gateway import Gateway
import config
from protocol import (
    PROTOCOL_VERSION,
    PKT_DATA,
    SENSOR_PAYLOAD_SIZE,
    PacketHeader,
    SensorPayload,
)


class MockRadioPacket:
    def __init__(self, data: bytes, rssi: int = -68, snr: float = 8.5):
        self.data = data
        self.rssi = rssi
        self.snr = snr


class TestGatewaySimulation(unittest.TestCase):
    def test_dashboard_file_exists_and_valid(self):
        dashboard_path = os.path.join(
            os.path.dirname(__file__), "dashboard.html"
        )
        self.assertTrue(os.path.exists(dashboard_path))
        with open(dashboard_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<!doctype html>", content)
        self.assertIn("LoRaForge 2 | Mine Monitoring", content)
        self.assertIn("/api/nodes", content)

    def test_gateway_node_processing_and_json(self):
        gateway = Gateway(simulate=True)

        # Before any packets, both nodes are offline and unseen
        initial_json = json.loads(gateway.get_nodes_json())
        self.assertEqual(len(initial_json), 2)
        self.assertEqual(initial_json[0]["id"], 1)
        self.assertFalse(initial_json[0]["online"])
        self.assertEqual(initial_json[0]["lastSeen"], "never")
        self.assertEqual(initial_json[1]["id"], 2)
        self.assertFalse(initial_json[1]["online"])

        # Send SYNC
        gateway.send_sync()
        self.assertEqual(gateway.sync_messages_sent, 1)

        # Simulate receiving packet from Node 1
        hdr1 = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_DATA,
            node_id=1,
            gateway_id=0,
            sequence=1,
            frame_number=0,
            payload_length=SENSOR_PAYLOAD_SIZE,
        )
        sensor1 = SensorPayload(
            temperature_x10=248,  # 24.8 °C
            pressure_pa=101310,   # 1013.10 hPa
            gas_adc=450,
            flame=0,
            vibration=0,
            accel_x=10,           # 0.10 g
            accel_y=-5,           # -0.05 g
            accel_z=98,           # 0.98 g
            uptime_seconds=120,
        )
        raw_pkt1 = hdr1.pack() + sensor1.pack()
        mock_pkt1 = MockRadioPacket(raw_pkt1, rssi=-64, snr=9.2)

        gateway.process_packet(mock_pkt1)

        # Check JSON response after Node 1 packet
        nodes_json = json.loads(gateway.get_nodes_json())
        n1 = nodes_json[0]
        self.assertEqual(n1["id"], 1)
        self.assertTrue(n1["online"])
        self.assertEqual(n1["temperature"], 248)
        self.assertEqual(n1["pressure"], 101310)
        self.assertEqual(n1["gas"], 450)
        self.assertFalse(n1["flame"])
        self.assertFalse(n1["vibration"])
        self.assertEqual(n1["acceleration"]["x"], 0.10)
        self.assertEqual(n1["acceleration"]["y"], -0.05)
        self.assertEqual(n1["acceleration"]["z"], 0.98)
        self.assertEqual(n1["packets"], 1)
        self.assertEqual(n1["missed"], 0)
        self.assertEqual(n1["rssi"], -64)
        self.assertEqual(n1["snr"], 9.2)
        self.assertIn("s ago", n1["lastSeen"])

        # Node 2 packet with sequence skip (simulate missed packets)
        hdr2 = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_DATA,
            node_id=2,
            gateway_id=0,
            sequence=1,
            frame_number=0,
            payload_length=SENSOR_PAYLOAD_SIZE,
        )
        sensor2 = SensorPayload(
            temperature_x10=210,
            pressure_pa=100900,
            gas_adc=120,
            flame=1,
            vibration=1,
            accel_x=0,
            accel_y=0,
            accel_z=100,
            uptime_seconds=500,
        )
        raw_pkt2 = hdr2.pack() + sensor2.pack()
        gateway.process_packet(MockRadioPacket(raw_pkt2, rssi=-70, snr=7.1))

        # Node 2 sends sequence 4 (missed sequences 2 and 3 -> missed count = 2)
        hdr2_missed = PacketHeader(
            version=PROTOCOL_VERSION,
            type=PKT_DATA,
            node_id=2,
            gateway_id=0,
            sequence=4,
            frame_number=1,
            payload_length=SENSOR_PAYLOAD_SIZE,
        )
        gateway.process_packet(
            MockRadioPacket(hdr2_missed.pack() + sensor2.pack(), rssi=-71, snr=6.8)
        )

        nodes_json2 = json.loads(gateway.get_nodes_json())
        n2 = nodes_json2[1]
        self.assertEqual(n2["id"], 2)
        self.assertTrue(n2["online"])
        self.assertEqual(n2["packets"], 2)
        self.assertEqual(n2["missed"], 2)
        self.assertTrue(n2["flame"])
        self.assertTrue(n2["vibration"])


if __name__ == "__main__":
    unittest.main()
