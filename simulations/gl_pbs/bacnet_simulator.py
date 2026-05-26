#!/usr/bin/env python
"""
AIBMS Plant Simulator — BACnet DDC simulator entry point.

Simulates a plant with AHUs, Chillers, Pumps, VAVs and other equipment.
Reads deployment config from JSON/CSV and exposes them as BACnet objects
on the configured port.  A lightweight web UI (HTTP) shows live values.

Usage
-----
  python bacnet_simulator.py
      (uses CBDeploymentDetails.json, port 2001, web UI 7090)

  python bacnet_simulator.py <deployFile> <bacnetPort> <webPort>
  python bacnet_simulator.py <deployFile> <bacnetPort> <webPort> <defaultIP>
  python bacnet_simulator.py <deployFile> <bacnetPort> <webPort> <defaultIP> <siteCSV>

Architecture
------------
simulator/config/sim_config.py     — SimulatorConfig dataclass (CLI → typed fields)
simulator/equipment/registry.py    — EquipmentRegistry  (replaces glEqpObjects globals)
simulator/equipment/loader.py      — EquipmentLoader    (JSON/CSV → BACnet objects)
simulator/objects/writable_objects.py — 7 custom writable BACnet types + factory
simulator/bacnet/application.py    — SimulatorApplication  (BACnet protocol)
simulator/bacnet/pulse_task.py     — PulseTask  (recurring value updates)
simulator/bacnet/console.py        — WhoIsIAmConsoleCmd  (interactive console)
simulator/http/handler.py          — SimulatorHttpHandler  (web UI + REST)
simulator/http/server.py           — ThreadedSimulatorServer  (HTTP server)
"""
import logging
import sys

from bacpypes.basetypes import DateTime, LogRecord, LogRecordLogDatum, StatusFlags
from bacpypes.core import enable_sleeping, run
from bacpypes.local.device import LocalDeviceObject
from bacpypes.object import TrendLogObject
from bacpypes.primitivedata import Date, Real, Time

from glDASLibrary import loadCodeBook, loadParamsJSON

from simulator.bacnet.application import SimulatorApplication
from simulator.bacnet.console import WhoIsIAmConsoleCmd
from simulator.bacnet.pulse_task import PulseTask
from simulator.config.sim_config import SimulatorConfig
from simulator.equipment.loader import EquipmentLoader
from simulator.equipment.registry import EquipmentRegistry
from simulator.http.server import start_http_server
from core.network_utils import get_local_ip_address, is_local_ip

###############################################################
# LOGGING

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)
logger = logging.getLogger('SimulatorMain')

###############################################################


def main() -> None:
    print('Welcome to Graylinx BACnet Plant Simulator!')
    print('Number of arguments:', len(sys.argv), 'arguments.')

    config = SimulatorConfig.from_argv(sys.argv)
    logger.info(
        'Config: port=%s webUI=%d deploy=%s ethernet=%s ip=%s',
        config.bacnet_port, config.web_ui_port,
        config.deployment_file, config.use_ethernet, config.default_ip,
    )

    # ── load codebook ──────────────────────────────────────────────────────────
    eqp_param_objects: dict = {}
    eqp_type_name_to_code: dict = {}
    if config.use_full_gl_code:
        [eqp_param_objects, eqp_type_name_to_code, _] = loadCodeBook('./data/CBParameters.csv')
        logger.info('Codebook loaded. Type-to-code: %s', eqp_type_name_to_code)
    else:
        loadParamsJSON()

    # ── equipment registry + loader ────────────────────────────────────────────
    registry = EquipmentRegistry()
    loader = EquipmentLoader(
        registry=registry,
        eqp_param_objects=eqp_param_objects,
        eqp_type_name_to_code=eqp_type_name_to_code,
        use_full_gl_code=config.use_full_gl_code,
    )

    loader.load_deployment_details(config.deployment_file, config.gls_file)

    if config.site_objects_file:
        loader.load_site_objects(config.site_objects_file)

    # ── network address ────────────────────────────────────────────────────────
    if config.default_ip:
        if not is_local_ip(config.default_ip):
            logger.error(
                'ERROR: defaultIP %s is not assigned to any local interface. Stopping.',
                config.default_ip,
            )
            sys.exit(1)
        my_address = '{}:{}'.format(config.default_ip, config.bacnet_port)
    else:
        detected_ip = get_local_ip_address(
            use_ethernet=config.use_ethernet,
            auto_detect=True,
        ) or '127.0.0.1'
        my_address = '{}:{}'.format(detected_ip, config.bacnet_port)
    logger.info('BACnet address: %s', my_address)

    # ── BACnet device + application ────────────────────────────────────────────
    this_device = LocalDeviceObject(
        objectName=config.device_name,
        objectIdentifier=config.device_object_id,
        maxApduLengthAccepted=1024,
        segmentationSupported='segmentedBoth',
        vendorIdentifier=15,
    )
    logger.info('LocalDeviceObject: %s', this_device)

    this_application = SimulatorApplication(this_device, my_address)

    # Register all equipment parameter objects
    for obj in registry.all_bacnet_objects():
        this_application.add_object(obj)

    # One shared trend-log object
    log_datum = LogRecordLogDatum(realValue=Real(32.0))
    log_record = LogRecord(
        timestamp=DateTime(date=Date().now().value, time=Time().now().value),
        logDatum=log_datum,
        statusFlags=StatusFlags([0, 0, 0, 0]),
    )
    trend_log = TrendLogObject(
        objectIdentifier=('trendLog', 1968),
        objectName='Special_Trend_Log',
        logBuffer=[log_record],
    )
    this_application.add_object(trend_log)
    logger.info('Objects registered: %d', len(list(this_device.objectList)))

    # ── HTTP web UI ────────────────────────────────────────────────────────────
    start_http_server(config.web_ui_port, registry, my_address, eqp_param_objects)

    # ── recurring value simulation ─────────────────────────────────────────────
    pulse_task = PulseTask(registry=registry, increment=1, interval_ms=10_000)
    logger.info('PulseTask installed: %r', pulse_task)

    # ── interactive console ────────────────────────────────────────────────────
    console = WhoIsIAmConsoleCmd(this_application)
    logger.info('Console ready: %r', console)

    # ── BACnet event loop ──────────────────────────────────────────────────────
    logger.info(
        'Simulator running — BACnet: %s  Web UI: http://0.0.0.0:%d',
        my_address, config.web_ui_port,
    )
    enable_sleeping()
    run()
    logger.debug('fini')


###############################################################
if __name__ == '__main__':
    main()
