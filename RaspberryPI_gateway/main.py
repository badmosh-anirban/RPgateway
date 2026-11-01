#!/usr/bin/env python3
"""
CLI entry point for Raspberry Pi LoRa TDMA Gateway.
"""

import argparse
import sys
import config
from gateway import Gateway


def main():
    parser = argparse.ArgumentParser(
        description="LoRa TDMA Single Channel Gateway on Raspberry Pi (radiogem)"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode without requiring SX1262 hardware",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.WEB_PORT,
        help=f"Web dashboard HTTP port (default: {config.WEB_PORT})",
    )
    parser.add_argument(
        "--superframe",
        type=int,
        default=config.SUPERFRAME_MS,
        help=f"Superframe duration in ms (default: {config.SUPERFRAME_MS})",
    )
    parser.add_argument(
        "--freq",
        type=float,
        default=config.LORA_FREQUENCY_MHZ,
        help=f"LoRa frequency in MHz (default: {config.LORA_FREQUENCY_MHZ})",
    )
    parser.add_argument(
        "--bw",
        type=float,
        default=config.LORA_BANDWIDTH_KHZ,
        help=f"LoRa bandwidth in kHz (default: {config.LORA_BANDWIDTH_KHZ})",
    )
    parser.add_argument(
        "--sf",
        type=int,
        default=config.LORA_SPREADING_FACTOR,
        help=f"LoRa spreading factor (default: {config.LORA_SPREADING_FACTOR})",
    )
    parser.add_argument(
        "--cr",
        type=int,
        default=config.LORA_CODING_RATE,
        help=f"LoRa coding rate denominator (default: {config.LORA_CODING_RATE})",
    )
    parser.add_argument(
        "--power",
        type=int,
        default=config.LORA_OUTPUT_POWER_DBM,
        help=f"LoRa TX output power in dBm (default: {config.LORA_OUTPUT_POWER_DBM})",
    )
    parser.add_argument(
        "--spi-ch",
        type=int,
        default=config.SPI_CHANNEL,
        help=f"SPI Channel (default: {config.SPI_CHANNEL})",
    )
    parser.add_argument(
        "--nss",
        type=int,
        default=config.PIN_NSS,
        help=f"NSS pin (default: {config.PIN_NSS})",
    )
    parser.add_argument(
        "--dio1",
        type=int,
        default=config.PIN_DIO1,
        help=f"DIO1 pin (default: {config.PIN_DIO1})",
    )
    parser.add_argument(
        "--rst",
        type=int,
        default=config.PIN_RST,
        help=f"Reset pin (default: {config.PIN_RST})",
    )
    parser.add_argument(
        "--busy",
        type=int,
        default=config.PIN_BUSY,
        help=f"Busy pin (default: {config.PIN_BUSY})",
    )
    args = parser.parse_args()

    # Apply command-line overrides to config
    config.WEB_PORT = args.port
    config.SUPERFRAME_MS = args.superframe
    config.LORA_FREQUENCY_MHZ = args.freq
    config.LORA_BANDWIDTH_KHZ = args.bw
    config.LORA_SPREADING_FACTOR = args.sf
    config.LORA_CODING_RATE = args.cr
    config.LORA_OUTPUT_POWER_DBM = args.power
    config.SPI_CHANNEL = args.spi_ch
    config.PIN_NSS = args.nss
    config.PIN_DIO1 = args.dio1
    config.PIN_RST = args.rst
    config.PIN_BUSY = args.busy

    print("=" * 65)
    print(" LoRa TDMA Single-Channel Gateway (Raspberry Pi)")
    print(f" Frequency: {config.LORA_FREQUENCY_MHZ} MHz | SF{config.LORA_SPREADING_FACTOR} | BW {config.LORA_BANDWIDTH_KHZ} kHz")
    print(f" TDMA Superframe: {config.SUPERFRAME_MS} ms | Nodes: {config.NODE_COUNT}")
    print(f" Web Dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}/")
    print(f" Mode: {'SIMULATION' if args.simulate else 'HARDWARE (radiogem SX1262)'}")
    print("=" * 65)

    gateway = Gateway(simulate=args.simulate)
    gateway.start()


if __name__ == "__main__":
    main()

