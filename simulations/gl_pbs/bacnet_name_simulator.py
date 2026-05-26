#!/usr/bin/env python
"""
AIBMS Plant Simulator — Name-Handler BACnet DDC simulator.

Reads data/eqp_name_handling.csv and exposes each row as a BACnet
object whose objectName is the gl_code field (name-handler approach).

This lets the PBS bacnet_reader (USE_OBJECT_NAME_HANDLER = True in
GLBACpypes.ini) match returned objectNames directly to GL codes
without any post-read remapping layer.

Usage
-----
  python bacnet_name_simulator.py
      Simulate DDC01 on 127.0.0.1:2001, web UI on 7091

  python bacnet_name_simulator.py <ddc_id> <bacnet_port> <web_port>
  python bacnet_name_simulator.py <ddc_id> <bacnet_port> <web_port> <ip>
  python bacnet_name_simulator.py <ddc_id> <bacnet_port> <web_port> <ip> <csv_file>

Arguments
---------
  ddc_id       DDC to simulate, e.g. DDC01 or DDC14.
               Default: DDC01
  bacnet_port  UDP port for BACnet/IP.
               Default: 2001
  web_port     TCP port for the live web dashboard.
               Default: 7091
  ip           Local IP address to bind.
               Default: auto-detected
  csv_file     Path to eqp_name_handling.csv.
               Default: data/eqp_name_handling.csv

Architecture
------------
simulator/equipment/name_handler_loader.py  — CSV → BACnet objects
simulator/equipment/registry.py             — EquipmentRegistry
simulator/objects/writable_objects.py       — writable BACnet types
simulator/bacnet/application.py             — SimulatorApplication
simulator/bacnet/pulse_task.py              — recurring value updates
simulator/bacnet/console.py                 — interactive console
simulator/http/server.py                    — web dashboard
"""
import logging
import sys
from dataclasses import dataclass
from typing import Optional

from bacpypes.basetypes import DateTime, LogRecord, LogRecordLogDatum, StatusFlags
from bacpypes.core import enable_sleeping, run
from bacpypes.local.device import LocalDeviceObject
from bacpypes.object import TrendLogObject
from bacpypes.primitivedata import Date, Real, Time

from simulator.bacnet.application import SimulatorApplication
from simulator.bacnet.console import WhoIsIAmConsoleCmd
from simulator.bacnet.pulse_task import PulseTask
from simulator.equipment.name_handler_loader import NameHandlerLoader
from simulator.equipment.registry import EquipmentRegistry
from simulator.http.server import start_http_server
from core.network_utils import get_local_ip_address, is_local_ip

###############################################################
# LOGGING

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)
logger = logging.getLogger('NameSimMain')

###############################################################


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class NameSimConfig:
    """CLI configuration for the name-handler simulator."""
    ddc_id:      str           = 'DDC01'
    bacnet_port: str           = '2001'
    web_ui_port: int           = 7091
    ip:          Optional[str] = None
    csv_file:    str           = 'data/eqp_name_handling.csv'
    no_console:  bool          = False   # set by --no-console (used by launcher)

    @classmethod
    def from_argv(cls, argv) -> 'NameSimConfig':
        cfg = cls()
        positional = [a for a in argv[1:] if a != '--no-console']
        cfg.no_console = '--no-console' in argv

        if len(positional) >= 1:
            cfg.ddc_id = positional[0].upper()
        if len(positional) >= 2:
            cfg.bacnet_port = positional[1]
        if len(positional) >= 3:
            cfg.web_ui_port = int(positional[2])
        # positional[3] is ip if it looks like a dotted IP, otherwise csv_file
        if len(positional) >= 4:
            if _looks_like_ip(positional[3]):
                cfg.ip = positional[3]
                if len(positional) >= 5:
                    cfg.csv_file = positional[4]
            else:
                cfg.csv_file = positional[3]
        return cfg

    @property
    def device_object_id(self) -> int:
        return int(self.bacnet_port)

    @property
    def device_name(self) -> str:
        return 'NameSim_{}_{}'.format(self.ddc_id, self.bacnet_port)


# ── Main ───────────────────────────────────────────────────────────────────────

def _looks_like_ip(s: str) -> bool:
    """True if s looks like a dotted IPv4 address (e.g. 192.168.1.1)."""
    import re
    return bool(re.match(r'^\d{1,3}(\.\d{1,3}){3}', s))


def _read_ini_ip(ini_file: str = 'config/GLBACpypes.ini') -> Optional[str]:
    """Read defaultIPAddress from GLBACpypes.ini; return None if not found."""
    import configparser
    try:
        c = configparser.ConfigParser()
        c.read(ini_file)
        if 'BACpypes' in c:
            ip = c['BACpypes'].get('defaultIPAddress', '').strip()
            return ip or None
    except Exception:
        pass
    return None


def main() -> None:
    print('Welcome to Graylinx BACnet Name-Handler Simulator!')
    print('Arguments:', sys.argv)

    config = NameSimConfig.from_argv(sys.argv)
    logger.info(
        'Config: ddc=%s  port=%s  web=%d  ip=%s  csv=%s',
        config.ddc_id, config.bacnet_port, config.web_ui_port,
        config.ip, config.csv_file,
    )

    # ── load objects from eqp_name_handling.csv ────────────────────────────────
    registry = EquipmentRegistry()
    loader = NameHandlerLoader(registry=registry, ddc_id=config.ddc_id)
    loader.load(config.csv_file)

    # ── resolve BACnet IP address ──────────────────────────────────────────────
    ip = config.ip or _read_ini_ip()
    if ip:
        if not is_local_ip(ip):
            logger.error(
                'IP %s is not assigned to any local interface — stopping.', ip,
            )
            sys.exit(1)
        my_address = '{}:{}'.format(ip, config.bacnet_port)
    else:
        detected = get_local_ip_address(use_ethernet=False, auto_detect=True) or '127.0.0.1'
        my_address = '{}:{}'.format(detected, config.bacnet_port)
    logger.info('BACnet address: %s', my_address)

    # ── BACnet device ──────────────────────────────────────────────────────────
    this_device = LocalDeviceObject(
        objectName=config.device_name,
        objectIdentifier=config.device_object_id,
        maxApduLengthAccepted=1024,
        segmentationSupported='segmentedBoth',
        vendorIdentifier=15,
    )
    logger.info('LocalDeviceObject: %s', this_device)

    this_application = SimulatorApplication(this_device, my_address)

    for obj in registry.all_bacnet_objects():
        this_application.add_object(obj)

    # One shared trend-log object (required by some readers)
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

    # ── HTTP web dashboard ─────────────────────────────────────────────────────
    start_http_server(config.web_ui_port, registry, my_address, {})

    # ── recurring value simulation ─────────────────────────────────────────────
    pulse_task = PulseTask(registry=registry, increment=1, interval_ms=10_000)
    logger.info('PulseTask installed: %r', pulse_task)

    # ── interactive console (skipped when launched by bacnet_name_launcher) ───
    if not config.no_console:
        console = WhoIsIAmConsoleCmd(this_application)
        logger.info('Console ready: %r', console)
    else:
        logger.info('Console disabled (--no-console).')

    # ── BACnet event loop ──────────────────────────────────────────────────────
    logger.info(
        'Name-Handler Simulator running — DDC=%s  BACnet=%s  Web=http://0.0.0.0:%d',
        config.ddc_id, my_address, config.web_ui_port,
    )
    enable_sleeping()
    run()
    logger.debug('fini')


###############################################################
if __name__ == '__main__':
    main()
