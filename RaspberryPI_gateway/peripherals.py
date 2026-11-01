"""
Peripherals management (LED, Buzzer, SSD1306 OLED) for Raspberry Pi Gateway.
Uses gpiozero for GPIO when available, with graceful fallbacks.
"""

import time
import logging
from typing import List, Optional, Any

from config import (
    GATEWAY_LED_PIN,
    GATEWAY_LED_BLINK_MS,
    BUZZER_PIN,
    BUZZER_ON_TIME_MS,
    ENABLE_OLED,
    OLED_I2C_PORT,
    OLED_ADDRESS,
    DISPLAY_UPDATE_INTERVAL_MS,
)

logger = logging.getLogger("GatewayPeripherals")

# Check for gpiozero
try:
    from gpiozero import LED, Buzzer, OutputDevice
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    LED = None
    Buzzer = None
    OutputDevice = None


class PeripheralsManager:
    def __init__(self):
        self.led: Optional[Any] = None
        self.buzzer: Optional[Any] = None
        self.display: Optional[Any] = None

        self.led_blinking: bool = False
        self.led_off_at: float = 0.0

        self.buzzer_active: bool = False
        self.buzzer_off_at: float = 0.0

        self.last_display_update: float = 0.0

        self._init_gpio()
        if ENABLE_OLED:
            self._init_oled()

    def _init_gpio(self):
        if not GPIOZERO_AVAILABLE:
            if GATEWAY_LED_PIN is not None or BUZZER_PIN is not None:
                logger.warning(
                    "gpiozero library not installed. LED and Buzzer hardware control disabled. "
                    "Install with: pip install gpiozero"
                )
            return

        # Initialize LED
        if GATEWAY_LED_PIN is not None:
            try:
                self.led = LED(GATEWAY_LED_PIN)
                self.led.off()
                logger.info(f"Initialized Gateway LED on GPIO {GATEWAY_LED_PIN}")
            except Exception as e:
                logger.error(f"Failed to initialize LED on GPIO {GATEWAY_LED_PIN}: {e}")
                self.led = None

        # Initialize Buzzer
        if BUZZER_PIN is not None:
            try:
                # Active buzzer: High turns buzzer on
                self.buzzer = OutputDevice(BUZZER_PIN, active_high=True, initial_value=False)
                logger.info(f"Initialized Active Buzzer on GPIO {BUZZER_PIN}")
            except Exception as e:
                logger.error(f"Failed to initialize Buzzer on GPIO {BUZZER_PIN}: {e}")
                self.buzzer = None

    def _init_oled(self):
        try:
            # Attempt to import luma.oled
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            serial = i2c(port=OLED_I2C_PORT, address=OLED_ADDRESS)
            self.display = ssd1306(serial, width=128, height=64)
            logger.info("SSD1306 OLED display initialized via luma.oled")
        except ImportError:
            logger.warning("luma.oled not installed. OLED display disabled.")
            self.display = None
        except Exception as e:
            logger.error(f"Failed to initialize OLED display: {e}")
            self.display = None

    def blink_led(self):
        if self.led is not None:
            try:
                self.led.on()
            except Exception as e:
                logger.error(f"Error turning LED on: {e}")
        self.led_blinking = True
        self.led_off_at = time.monotonic() + (GATEWAY_LED_BLINK_MS / 1000.0)

    def trigger_buzzer(self):
        if self.buzzer is not None:
            try:
                self.buzzer.on()
            except Exception as e:
                logger.error(f"Error turning Buzzer on: {e}")
        self.buzzer_active = True
        self.buzzer_off_at = time.monotonic() + (BUZZER_ON_TIME_MS / 1000.0)
        logger.info("[ALERT] Buzzer triggered!")

    def update(self):
        now = time.monotonic()

        # Update LED state
        if self.led_blinking and now >= self.led_off_at:
            if self.led is not None:
                try:
                    self.led.off()
                except Exception:
                    pass
            self.led_blinking = False

        # Update Buzzer state
        if self.buzzer_active and now >= self.buzzer_off_at:
            if self.buzzer is not None:
                try:
                    self.buzzer.off()
                except Exception:
                    pass
            self.buzzer_active = False

    def update_display(self, sync_sent: int, frame_number: int, nodes: List[Any]):
        if self.display is None:
            return

        now = time.monotonic()
        if (now - self.last_display_update) * 1000.0 < DISPLAY_UPDATE_INTERVAL_MS:
            return
        self.last_display_update = now

        try:
            from PIL import Image, ImageDraw, ImageFont
            image = Image.new("1", (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()

            draw.text((0, 0), f"SYNC:{sync_sent} | F:{frame_number}", font=font, fill=255)

            y = 16
            for node in nodes[:2]:
                st_str = "ON " if node.online else "OFF"
                draw.text(
                    (0, y),
                    f"N{node.node_id}: {st_str} P:{node.packets_received} M:{node.packets_missed}",
                    font=font,
                    fill=255,
                )
                if node.seen:
                    draw.text(
                        (0, y + 10),
                        f"  R:{node.rssi} | S:{node.snr:.1f}",
                        font=font,
                        fill=255,
                    )
                else:
                    draw.text((0, y + 10), "  R:-- S:--", font=font, fill=255)
                y += 24

            self.display.display(image)
        except Exception as e:
            logger.debug(f"OLED render error: {e}")

    def close(self):
        if self.led is not None:
            try:
                self.led.off()
                self.led.close()
            except Exception:
                pass
            self.led = None

        if self.buzzer is not None:
            try:
                self.buzzer.off()
                self.buzzer.close()
            except Exception:
                pass
            self.buzzer = None

        if self.display is not None:
            try:
                self.display.cleanup()
            except Exception:
                pass
            self.display = None

