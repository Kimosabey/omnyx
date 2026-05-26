#!/usr/bin/env python
"""
bacnet_reader — BACnet multi-device threaded data acquisition.

Reads BACnet points from multiple devices concurrently, detects
Change-of-Value, and posts results to a web endpoint and/or database.

Usage:
    python bacnet_reader.py --ini config/GLBACpypes.ini

Entry point only.  All business logic lives in:
  config/app_config.py          — typed configuration (replaces GL_GLOBALS)
  core/point_list_store.py      — per-device state and point list management
  core/cov_checker.py           — Change-of-Value detection
  core/data_publisher.py        — HTTP notification payloads
  core/db_writer.py             — database insertion
  bacnet/read_strategy.py       — RPM and single-property read strategies
  bacnet/read_thread.py         — per-device thread coordinator
  bacnet/thread_supervisor.py   — retry loop and lifecycle management
"""
from __future__ import annotations

import sys
import time
import threading
from threading import Event

from bacpypes.app import BIPSimpleApplication
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.core import deferred, run, stop
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address
from bacpypes.task import RecurringTask

from config.app_config import AppConfig
from core.cov_checker import CoVChecker
from core.data_publisher import DataPublisher
from core.db_writer import DatabaseWriter
from core.point_list_store import PointListStore
from bacnet.read_strategy import RPMReadStrategy, SingleReadStrategy
from core.network_utils import is_local_ip
from core.network_watchdog import NetworkWatchdog
from bacnet.read_thread import ReadPointListThread
from bacnet.thread_supervisor import ThreadSupervisor

from glDASLibrary import (
    createDBConnectionPool,
    getLocalIPAddress,
    prepareConfigurationFromCodeBook,
    prepareDeploymentConfiguration,
    prepareEquipmentParameterDataFile,
    preparePointListFromNH,
    printTrace,
    setConfigurationDetails,
)
from glWebLibrary import initializeWebServer

# ── Heartbeat ──────────────────────────────────────────────────────────────
# Path must match HEARTBEAT_FILE in ddc_watchdog.py
HEARTBEAT_FILE = "heartbeat.txt"


def _write_heartbeat() -> None:
    """Touch HEARTBEAT_FILE with the current timestamp so ddc_watchdog.py
    knows the reader is alive and actively dispatching read batches."""
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass   # non-fatal; watchdog will notice the stale file


# ── BatchProcessor ─────────────────────────────────────────────────────────

class BatchProcessor:
    """
    Orchestrates one complete read cycle across all devices.

    Owns the BACnet application handle (replaces the global this_application)
    and creates all per-cycle service objects (strategy, CoVChecker, etc.).

    Replaces the module-level processCompleteBatch() function.
    """

    def __init__(
        self,
        bacnet_app: BIPSimpleApplication,
        config: AppConfig,
        store: PointListStore,
        connection_pool,
    ) -> None:
        self.bacnet_app = bacnet_app
        self.config = config
        self.store = store
        self.connection_pool = connection_pool

        # mutable counters managed by GLProcessLoop
        self.time_interval_counter: int = -1
        self.current_read_cycle: int = 0

    # ── public ────────────────────────────────────────────────────────────

    def process_complete_batch(self) -> None:
        """
        Create a ReadPointListThread per device and hand them to a
        ThreadSupervisor.  Mirrors processCompleteBatch() from the original.
        """
        thread_list: list = []
        publisher = self._make_publisher()
        db_writer = self._make_db_writer()
        names_ready = self.store.names_ready

        default_interval_secs = int(60 * self.config.inter_batch_interval)

        for addr_raw, points, prev_vals, list_index in self.store.iter_batch_entries(
            time_interval_counter=self.time_interval_counter,
            allow_multiple_sampling_rates=self.config.allow_multiple_sampling_rates,
            default_interval_seconds=default_interval_secs,
        ):
            strategy = self._make_strategy()
            cov_checker = CoVChecker(
                previous_values=prev_vals,
                heartbeat_minutes=self.config.data_acquisition_heartbeat_minutes,
                threshold_percent=self.config.cov_threshold_percent,
                table_name_length=self.config.database_table_name_length,
            )
            thread = ReadPointListThread(
                device_address=addr_raw,
                point_list=points,
                strategy=strategy,
                cov_checker=cov_checker,
                data_publisher=publisher,
                db_writer=db_writer,
                bacnet_app=self.bacnet_app,
                config=self.config,
                timeout=self.config.data_acquisition_timeout_secs,
                list_index=list_index,
                names_ready=names_ready,
            )
            thread_list.append(thread)

        if not thread_list:
            printTrace('process_complete_batch — no devices triggered (counter={}, names_ready={})'.format(
                self.time_interval_counter, self.store.names_ready
            ))
            return

        printTrace('process_complete_batch — starting {} device threads'.format(len(thread_list)))
        supervisor = ThreadSupervisor(
            thread_list=thread_list,
            point_list_store=self.store,
            config=self.config,
            max_attempts=self.config.data_acquisition_max_retry_attempts,
            completion_event=Event(),
            post_complete_callback=self._make_post_complete_callback(),
        )
        deferred(supervisor.start)

    # ── factory helpers ───────────────────────────────────────────────────

    def _make_strategy(self):
        if self.config.use_read_property_multiple:
            return RPMReadStrategy(
                use_object_name_handler=self.config.use_object_name_handler
            )
        return SingleReadStrategy()

    def _make_publisher(self) -> DataPublisher:
        return DataPublisher(
            post_url=self.config.post_url,
            notify_mode=self.config.notify_read_data,
            web_post_timeout_secs=self.config.web_post_timeout_secs,
        )

    def _make_db_writer(self) -> DatabaseWriter:
        return DatabaseWriter(
            connection_pool=self.connection_pool,
            use_per_equipment_table=self.config.use_per_equipment_table,
            database_table_name=self.config.database_table_name,
            use_multiple_tables=self.config.use_multiple_tables,
            create_equipment_table=self.config.create_equipment_table,
        )

    def _make_post_complete_callback(self):
        """
        Returns a one-shot callback that saves the equipment parameter file
        after (numberOfReadCycles - 1) cycles, then disables itself.
        Replaces the storeEquipmentParameterData block in ThreadSupervisor.
        """
        if (
            self.config.store_equipment_parameter_data
            and self.config.number_of_read_cycles != -1
            and self.current_read_cycle == self.config.number_of_read_cycles - 1
        ):
            config = self.config

            def _callback():
                prepareEquipmentParameterDataFile(
                    config.rpm_requests_file + '.json'
                )
                config.store_equipment_parameter_data = False

            return _callback
        return None


# ── GLProcessLoop ──────────────────────────────────────────────────────────

class GLProcessLoop(RecurringTask):
    """
    Recurring BACnet task that triggers a read batch on each tick.

    Owns the read-cycle counter (was the global current_read_cycle) and
    delegates batch work to BatchProcessor.
    """

    def __init__(
        self,
        interval_ms: float,
        batch_processor: BatchProcessor,
    ) -> None:
        if batch_processor.config.allow_multiple_sampling_rates:
            interval_ms = 1000  # 1 s granularity for multi-rate mode
        RecurringTask.__init__(self, interval_ms)
        self.install_task()
        self.batch_processor = batch_processor

    def process_task(self) -> None:
        bp = self.batch_processor
        cfg = bp.config

        bp.current_read_cycle += 1

        bp.time_interval_counter = int(bp.time_interval_counter + 1)
        if bp.time_interval_counter >= cfg.counter_limit:
            bp.time_interval_counter -= cfg.counter_limit

        if (
            cfg.number_of_read_cycles != -1
            and bp.current_read_cycle >= cfg.number_of_read_cycles
        ):
            printTrace('Stopping after {} cycles — current_read_cycle:{}'.format(
                cfg.number_of_read_cycles, bp.current_read_cycle
            ))
            self.suspend_task()
            stop()
        else:
            printTrace('process_task — counter:{}'.format(bp.time_interval_counter))
            bp.process_complete_batch()
            _write_heartbeat()


# ── Application entry point ────────────────────────────────────────────────

def main() -> None:
    printTrace('Program Started')

    # ── Parse INI / command-line args ─────────────────────────────────────
    args = ConfigArgumentParser(description=__doc__).parse_args()

    # setConfigurationDetails merges INI values into a GL_GLOBALS-shaped dict
    raw_config = setConfigurationDetails(args.ini)
    config = AppConfig.from_ini_dict(raw_config)

    printTrace('Configuration loaded')

    # ── Database connection pool ──────────────────────────────────────────
    connection_pool = None
    if config.insert_rm_data_into_db:
        connection_pool = createDBConnectionPool(
            mydatabase=config.ibms_database_name,
            dbuser=config.database_user,
            dbpassword=config.database_password,
            host=config.database_host,
        )

    # ── Deployment configuration ──────────────────────────────────────────
    if config.use_multiple_tables:
        prepareConfigurationFromCodeBook(
            glConfigFile=config.gl_codebook_csv,
            deplDtlsJSONFile=config.deployment_details_file,
            myConnectionPool=connection_pool,
        )
    else:
        prepareDeploymentConfiguration(config.deployment_config_file, connection_pool)

    # ── BACnet device object ──────────────────────────────────────────────
    this_device = LocalDeviceObject(
        objectName=args.ini['objectname'],
        objectIdentifier=int(args.ini['objectidentifier']),
        maxApduLengthAccepted=int(args.ini['maxapdulengthaccepted']),
        segmentationSupported=args.ini['segmentationsupported'],
        vendorIdentifier=int(args.ini['vendoridentifier']),
    )

    if config.default_ip_address and not is_local_ip(config.default_ip_address):
        printTrace(
            'ERROR: defaultIPAddress {} is not assigned to any local interface. Stopping.'.format(
                config.default_ip_address
            )
        )
        sys.exit(1)

    myaddress = getLocalIPAddress(
        config.my_bacnet_port,
        not config.discover_device_ip_address,
        noPort=False,
        defaultIp=config.default_ip_address,
        useEthernet=config.use_ethernet,
        autoDetectIp=not bool(config.default_ip_address),
    )
    printTrace('BACnet address: {}'.format(myaddress))

    # Extract just the IP portion (strip subnet mask and port) for watchdog
    watch_ip = (
        config.default_ip_address
        or myaddress.split('/')[0].split(':')[0]
    ).strip()

    # ── Point list (also initialises the name-handler lookup) ────────────
    rpm_list, name_list = preparePointListFromNH(
        fileName=config.rpm_requests_file,
        rpm=config.use_read_property_multiple,
        makeNameList=True,
        useLocalDDCSimulators=config.use_local_ddc_simulators,
        ddcmapper=config.controller_map,
        tblNameLength=config.database_table_name_length,
        batchSize=config.rpm_batch_size,
    )

    printTrace('preparePointListFromNH — rpm_list entries:{} name_list entries:{}'.format(
        len(rpm_list), len(name_list)
    ))
    if rpm_list:
        printTrace('  First rpm_list entry address: {}'.format(rpm_list[0][0]))
    else:
        printTrace('  WARNING: rpm_list is EMPTY — no devices to read!')

    store = PointListStore(
        rpm_list=rpm_list,
        name_list=name_list,
        names_ready=config.use_object_name_handler,
    )

    # ── Optional web server ───────────────────────────────────────────────
    if config.enable_pbs2_web:
        initializeWebServer(
            myWebPort=config.pbs2_web_port,
            mycallback=store.get_snapshot,
        )

    # ── BACnet restart loop ───────────────────────────────────────────────
    # On each iteration: bind the BACnet app, run, and — if the network
    # dropped — wait for it to come back and rebind automatically.
    while True:
        bacnet_app = BIPSimpleApplication(this_device, myaddress)

        for ip_port, networks in config.mstp_networks_map.items():
            bacnet_app.nsap.update_router_references(None, Address(ip_port), networks)

        batch_processor = BatchProcessor(
            bacnet_app=bacnet_app,
            config=config,
            store=store,
            connection_pool=connection_pool,
        )

        # Flag set by watchdog so the loop knows why run() returned
        network_lost = threading.Event()

        def _on_network_lost(_evt=network_lost):
            printTrace('Network lost — stopping BACnet event loop')
            _evt.set()
            stop()

        watchdog = NetworkWatchdog(ip_address=watch_ip, on_lost=_on_network_lost)
        watchdog.start()

        # ── Start acquisition ─────────────────────────────────────────
        printTrace('Read Cycle Started')
        if config.recurring_data_load:
            GLProcessLoop(
                interval_ms=config.inter_batch_interval * 60 * 1000,
                batch_processor=batch_processor,
            )
        else:
            batch_processor.process_complete_batch()

        run()          # blocks until stop() is called
        watchdog.stop()

        if not network_lost.is_set():
            # Normal exit (e.g. max read cycles reached)
            break

        # ── Network was lost; wait for it to come back ────────────────
        printTrace('Network lost — polling every 5 s for recovery...')
        try:
            bacnet_app.close_socket()
        except Exception:
            pass

        while not is_local_ip(watch_ip):
            time.sleep(5)

        printTrace('Network restored — restarting BACnet binding')


if __name__ == '__main__':
    main()
