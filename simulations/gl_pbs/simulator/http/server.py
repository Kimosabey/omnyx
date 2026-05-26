"""
server — ThreadedSimulatorServer + start_http_server().

SRP: Only responsible for creating and starting the HTTP server thread.
DIP: Registry, address, and codebook objects are injected; not read from globals.

Port of GLThreadedTCPServer and the initialize() function in
bacnet_simulator.py.
"""
from __future__ import annotations

import logging
import threading

try:
    from socketserver import ThreadingMixIn, TCPServer
except ImportError:
    from SocketServer import ThreadingMixIn, TCPServer  # type: ignore

from simulator.equipment.registry import EquipmentRegistry
from simulator.http.handler import SimulatorHttpHandler

logger = logging.getLogger(__name__)


class ThreadedSimulatorServer(ThreadingMixIn, TCPServer):
    """Threaded TCP server — each request runs in its own thread."""

    def server_bind(self) -> None:
        self.allow_reuse_address = True
        super().server_bind()


def start_http_server(
    port: int,
    registry: EquipmentRegistry,
    my_address: str,
    eqp_param_objects: dict,
) -> ThreadedSimulatorServer:
    """
    Configure the HTTP handler, create the server, and start a daemon thread.

    Port of initialize() with all global dependencies removed.

    Returns the server instance so the caller can shut it down if needed.
    """
    SimulatorHttpHandler.configure(registry, my_address, eqp_param_objects, web_port=port)

    server = ThreadedSimulatorServer(('0.0.0.0', port), SimulatorHttpHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    logger.info('HTTP simulator UI listening on port %d', port)
    return server
