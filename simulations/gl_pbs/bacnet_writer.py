#!/usr/bin/python
"""
bacnet_writer — HTTP-to-BACnet gateway entry point.

This file is intentionally minimal: it only wires together the components
from the refactored package structure and starts the BACnet event loop.

Run with:
    python bacnet_writer.py --ini config/GLBACpypes.ini [options]

Options
-------
--host HOST                     HTTP server bind address (default: localhost)
--port PORT                     HTTP server port (default: 7080)
--postroute URL                 URL to POST BACnet responses to
--qProcessIntervalInSeconds N   Queue poll interval in seconds (default: 1)
--defaultIPAddress IP           Local Ethernet IP for BACnet (default: 127.0.0.1)
--testBACnetIP IP               Fire test URLs against this IP at startup
--useObjectNameHandler BOOL     Enable glObjectNameHandler processing

Architecture (SOLID refactored)
--------------------------------
config/server_config.py   — ServerConfig dataclass
core/request_queue.py     — RequestQueue (FIFO for HTTP→BACnet requests)
core/response_poster.py   — ResponsePoster (HTTP POST for BACnet responses)
core/network_utils.py     — get_local_ip_address()
gateway/request_handler.py   — HttpRequestHandler + ThreadedTCPServer
gateway/request_parser.py    — parse_http_request() + parse_for_bacnet()
bacnet/service_context.py — ServiceContext + ObjectListContext
bacnet/process_loop.py    — ProcessLoop (RecurringTask)
bacnet/application.py     — BACnetServicesApplication
"""
###############################################################
# IMPORTS
import logging
import logging.config
import threading
import time

import urllib3
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.core import run, stop
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address

from bacnet.application import BACnetServicesApplication
from bacnet.process_loop import ProcessLoop
from bacnet.service_context import SubscriptionRegistry
from config.server_config import ServerConfig
from core.network_utils import get_local_ip_address
from core.request_queue import RequestQueue
from core.response_poster import ResponsePoster
from gateway.request_handler import HttpRequestHandler, ThreadedTCPServer

###############################################################
# LOGGING

logging.config.fileConfig('bacnet_writer.conf')
logger = logging.getLogger('MainLogger')

###############################################################
# MODULE-LEVEL SINGLETONS (set by initialize / start_bacnet_services)

_this_application: BACnetServicesApplication = None
_this_device: LocalDeviceObject = None
_process_loop: ProcessLoop = None
_config: ServerConfig = None

###############################################################
# HELPERS


def _prepare_configuration() -> tuple:
    """
    Parse CLI + INI arguments, build and return (args, ServerConfig).
    Port of prepareConfiguration() + GL_GLOBALS mutation.
    """
    parser = ConfigArgumentParser(description=__doc__)
    parser.add_argument('--host', type=str, default='localhost', help='HTTP server host')
    parser.add_argument('--port', type=int, default=7080, help='HTTP server port')
    parser.add_argument('--postroute', type=str,
                        default='https://localhost:443/v1/devices/bacnetevents',
                        help='POST response URL')
    parser.add_argument('--qProcessIntervalInSeconds', type=float, default=1.0,
                        help='Queue poll interval in seconds')
    parser.add_argument('--defaultIPAddress', type=str, default='127.0.0.1',
                        help='Local Ethernet IP address')
    parser.add_argument('--testBACnetIP', type=str, default=None,
                        help='IP address for firing test URLs at startup')
    parser.add_argument('--useObjectNameHandler', type=str, default=False,
                        help='Enable object name handler')
    args = parser.parse_args()
    config = ServerConfig.from_args(args)
    return args, config


def _fire_test_urls(config: ServerConfig, request_queue: RequestQueue) -> None:
    """Enqueue the default test URLs against the configured test IP."""
    from gateway.request_parser import parse_http_request
    for url_tpl in config.test_urls:
        req = parse_http_request(request_path=url_tpl.format(config.bacnet_test_device_ip))
        if len(req['request_parts']) > 2:
            request_queue.push(req)


###############################################################
# START / STOP


def _bind_bacnet_app(args, config: ServerConfig, process_loop: ProcessLoop) -> None:
    """
    Create (or recreate) the LocalDeviceObject and BACnetServicesApplication
    and wire them into *process_loop*.  Does NOT call run().

    Safe to call from a background thread to rebind after network recovery.
    """
    global _this_application, _this_device

    ini_address = getattr(args.ini, 'address', None) or config.default_ip_address
    effective_ip = ini_address.split('/')[0].strip()  # strip subnet mask if present

    # Wait for a valid network IP — poll every 5 s so we match the watchdog cadence
    while True:
        ip = get_local_ip_address(default_ip=effective_ip)
        if ip is not None:
            config.my_ip_address = ip
            break
        logger.warning('Network not ready — retrying in 5 s')
        time.sleep(5)

    _this_device = LocalDeviceObject(ini=args.ini)
    logger.info('LocalDeviceObject: %s', _this_device)

    poster = ResponsePoster(post_route=config.post_route)
    subscriptions = SubscriptionRegistry()

    _this_application = BACnetServicesApplication(
        device=_this_device,
        ip_address=config.my_ip_address,
        config=config,
        response_poster=poster,
        subscription_registry=subscriptions,
        resume_callback=process_loop.resume_and_dispatch,
    )

    # Static router table (site-specific; adapt as needed)
    _this_application.nsap.update_router_references(None, Address('192.168.1.102'), [10])
    _this_application.nsap.update_router_references(None, Address('192.168.1.103'), [12])
    _this_application.nsap.update_router_references(None, Address('192.168.1.104'), [14])

    process_loop.set_application(_this_application)
    logger.info('BACnet app bound to %s', config.my_ip_address)


def start_bacnet_services(args, config: ServerConfig, process_loop: ProcessLoop) -> None:
    """
    Bind the BACnet application and start the event loop.

    Port of startBACnetServices().
    """
    _bind_bacnet_app(args, config, process_loop)

    logger.info(
        'Server started at http://%s:%d — BACnet Device: %s',
        config.my_ip_address, config.port, _this_device,
    )
    run()


def stop_bacnet_services() -> None:
    """Tear down the BACnet application. Port of stopBACnetServices()."""
    global _this_application, _this_device
    if _this_application is not None:
        _this_application.close_socket()
    _this_application = None
    _this_device = None


###############################################################
# MAIN ENTRY POINT


def initialize() -> tuple:
    """
    Set up logging, parse config, create the request queue, HTTP server,
    and process loop.  Returns (args, config, request_queue, process_loop).

    Port of initialize() in bacnet_writer.py.
    """
    urllib3.disable_warnings()

    args, config = _prepare_configuration()

    # Request queue
    request_queue = RequestQueue()

    # Process loop (suspended until BACnet app is ready).
    # _bind_bacnet_app is run in a daemon thread so the ProcessLoop callback
    # (which runs on the BACnet event-loop thread) is never blocked by the
    # network-wait loop inside _bind_bacnet_app.
    def _rebind_in_thread():
        threading.Thread(
            target=lambda: _bind_bacnet_app(args, config, loop),
            name='BACnetRebind',
            daemon=True,
        ).start()

    loop = ProcessLoop(
        interval_ms=config.q_process_interval_secs * 1000,
        request_queue=request_queue,
        config=config,
        start_bacnet=_rebind_in_thread,
        stop_bacnet=stop_bacnet_services,
    )

    # HTTP server — inject queue before creating the server
    HttpRequestHandler.configure(request_queue, config,
                                 controller_map_json=args.ini.get('controllermap', ''))
    http_server = ThreadedTCPServer(('0.0.0.0', config.port), HttpRequestHandler)

    server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    server_thread.start()

    logger.info('HTTP server listening on port %d', config.port)
    return args, config, request_queue, loop


def main() -> None:
    print('Welcome to Graylinx Python BACnet Solution!')
    args, config, request_queue, loop = initialize()

    if config.bacnet_test_device_ip:
        _fire_test_urls(config, request_queue)

    start_bacnet_services(args, config, loop)


###############################################################
# STARTER
if __name__ == '__main__':
    main()
