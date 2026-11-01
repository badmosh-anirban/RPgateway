"""
Web server for Raspberry Pi Gateway Dashboard and Node API.
Uses Python's standard library ThreadingHTTPServer.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import threading
from typing import Callable, Optional

logger = logging.getLogger("GatewayWebServer")

DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")


class GatewayHTTPHandler(BaseHTTPRequestHandler):
    get_nodes_json_func: Optional[Callable[[], str]] = None
    dashboard_html_cache: Optional[bytes] = None

    def log_message(self, format, *args):
        # Silence default HTTP access logs or route to debug
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.handle_dashboard()
        elif self.path == "/api/nodes":
            self.handle_api_nodes()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_dashboard(self):
        try:
            if GatewayHTTPHandler.dashboard_html_cache is None:
                if os.path.exists(DASHBOARD_PATH):
                    with open(DASHBOARD_PATH, "rb") as f:
                        GatewayHTTPHandler.dashboard_html_cache = f.read()
                else:
                    self.send_error(500, "Dashboard HTML file missing")
                    return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(GatewayHTTPHandler.dashboard_html_cache)))
            self.end_headers()
            self.wfile.write(GatewayHTTPHandler.dashboard_html_cache)
        except Exception as e:
            logger.error(f"Error serving dashboard: {e}")
            self.send_error(500, f"Internal Error: {e}")

    def handle_api_nodes(self):
        try:
            if GatewayHTTPHandler.get_nodes_json_func:
                data = GatewayHTTPHandler.get_nodes_json_func()
            else:
                data = "[]"

            payload = data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            logger.error(f"Error serving /api/nodes: {e}")
            self.send_error(500, f"Internal Error: {e}")


class GatewayWebServer:
    def __init__(self, host: str, port: int, get_nodes_json_func: Callable[[], str]):
        self.host = host
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

        GatewayHTTPHandler.get_nodes_json_func = staticmethod(get_nodes_json_func)

    def start(self):
        try:
            self.server = ThreadingHTTPServer((self.host, self.port), GatewayHTTPHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Dashboard Web Server running at http://{self.host}:{self.port}/")
        except Exception as e:
            logger.error(f"Failed to start Dashboard Web Server on {self.host}:{self.port}: {e}")

    def stop(self):
        if self.server:
            logger.info("Stopping Web Server...")
            self.server.shutdown()
            self.server.server_close()
            self.server = None

