"""
ReadPointListThread — thin coordinator for a single device read cycle.

SRP: Orchestrates one read + post-processing by calling injected services.
DIP: All processing dependencies (strategy, cov_checker, publisher,
     db_writer, bacnet_app) are passed at construction — no globals.

Refactored from the monolithic ReadPointListThread in the original
bacnet_reader.py.  The BACnet protocol work is now in the strategy
classes; CoV, notification, and DB logic are in their own classes.
"""
from __future__ import annotations

from threading import Thread
from typing import TYPE_CHECKING, Optional

from glDASLibrary import getRequestUUID, getstrTimeNow, myprint, printTrace
from bacnet.read_strategy import RPM_NOT_SUPPORTED, RPMReadStrategy, SingleReadStrategy

if TYPE_CHECKING:
    from bacnet.read_strategy import AbstractReadStrategy
    from config.app_config import AppConfig
    from core.cov_checker import CoVChecker
    from core.data_publisher import DataPublisher
    from core.db_writer import DatabaseWriter

SUCCESS = 0


class ReadPointListThread(Thread):
    """
    Coordinates a single BACnet read cycle for one device.

    Lifecycle:
      1. start()  → run()
      2. run()    → strategy.prepare() + strategy.execute()
      3. On success, _post_process() → CoV → publish → DB write
    """

    def __init__(
        self,
        device_address: str,
        point_list: list,
        strategy: 'AbstractReadStrategy',
        cov_checker: 'CoVChecker',
        data_publisher: 'DataPublisher',
        db_writer: 'DatabaseWriter',
        bacnet_app,               # BIPSimpleApplication
        config: 'AppConfig',
        timeout: float = 20.0,
        attempt: int = 1,
        list_index: int = 0,
        names_ready: bool = False,
    ) -> None:
        super().__init__()
        self.device_address = device_address
        self.point_list = point_list
        self.strategy = strategy
        self.cov_checker = cov_checker
        self.data_publisher = data_publisher
        self.db_writer = db_writer
        self.bacnet_app = bacnet_app
        self.config = config
        self.timeout = timeout
        self.attempt = attempt
        self.list_index = list_index
        self.names_ready = names_ready

        # per-run state
        self.thread_id: str = getRequestUUID()
        self.point_values: dict = {}
        self.attempt_status: int = -1  # -1 pending, 0 = SUCCESS
        self.thread_dump: dict = {'initiated': getstrTimeNow()}
        # Set when RPM was rejected and we fell back to single reads.
        # Persists across clone() so retries skip RPM entirely.
        self._fallback_pairs: Optional[list] = None

    # ── Thread API ────────────────────────────────────────────────────────

    def run(self) -> None:
        self.thread_dump['started'] = getstrTimeNow()

        # Use pre-converted pairs when a previous attempt already determined
        # that this device does not support RPM.
        effective_list = (
            self._fallback_pairs
            if self._fallback_pairs is not None
            else self.point_list
        )
        self.strategy.prepare(effective_list, self.point_values)
        result = self.strategy.execute(
            self.bacnet_app,
            self.device_address,
            self.timeout,
            self.point_values,
            self.thread_dump,
        )

        # If the device explicitly rejected RPM, immediately retry with
        # individual ReadProperty requests so this cycle still succeeds.
        if result == RPM_NOT_SUPPORTED and isinstance(self.strategy, RPMReadStrategy):
            myprint(
                'RPM rejected by {} — retrying with ReadProperty'.format(
                    self.device_address
                )
            )
            single_pairs = self.strategy.to_single_pairs()
            fallback = SingleReadStrategy()
            self.point_values = {}
            fallback.prepare(single_pairs, self.point_values)
            result = fallback.execute(
                self.bacnet_app,
                self.device_address,
                self.timeout,
                self.point_values,
                self.thread_dump,
            )
            # Remember the fallback so clone() retries also skip RPM.
            self._fallback_pairs = single_pairs
            self.strategy = fallback

        self.attempt_status = result
        if result == SUCCESS and self.config.cov_computation_within_thread:
            self._post_process()

    # ── retry clone ───────────────────────────────────────────────────────

    def clone(self, new_timeout: float, next_attempt: int) -> 'ReadPointListThread':
        """
        Create a retry clone with doubled timeout.
        The cov_checker carries the same previous_values reference so
        CoV state accumulated in this attempt is preserved.
        _fallback_pairs is forwarded so the clone skips RPM if this attempt
        already determined that the device does not support it.
        """
        t = ReadPointListThread(
            device_address=self.device_address,
            point_list=self.point_list,
            strategy=self.strategy,
            cov_checker=self.cov_checker,   # shared state reference
            data_publisher=self.data_publisher,
            db_writer=self.db_writer,
            bacnet_app=self.bacnet_app,
            config=self.config,
            timeout=new_timeout,
            attempt=next_attempt,
            list_index=self.list_index,
            names_ready=self.names_ready,
        )
        t._fallback_pairs = self._fallback_pairs
        return t

    # ── thread dump ───────────────────────────────────────────────────────

    def get_thread_dump(
        self,
        params: list,
        prefix: str = '',
        suffix: str = '-',
        thread_prefix: str = '',
    ) -> str:
        """Port of ReadPointListThread.getThreadDump()."""
        get_param = lambda p: self.thread_dump.get(p, '-')
        if not thread_prefix:
            thread_prefix = self.device_address
        return '{},{},{},{},{}'.format(
            self.thread_id,
            prefix,
            thread_prefix,
            ','.join([get_param(p) for p in params]),
            suffix,
        )

    # ── post-processing ───────────────────────────────────────────────────

    def _post_process(self) -> None:
        """
        Orchestrate CoV detection → notification → DB write.
        Port of ReadPointListThread.postProcessResults().

        Called either from run() (when cov_computation_within_thread=True)
        or by ThreadSupervisor after join() (when False).
        """
        measured_time = self.thread_dump.get('device_responded', getstrTimeNow())
        cov_result = None

        # ── CoV / all-data notification ──────────────────────────────────
        if self.config.check_cov or self.config.notify_read_data == 'ONLY_COV':
            self.thread_dump['cov_requested'] = getstrTimeNow()
            cov_result = self.data_publisher.build_cov_payload(
                thread_id=self.thread_id,
                device_address=self.device_address,
                point_values=self.point_values,
                cov_checker=self.cov_checker,
                measured_time=measured_time,
                check_cov=self.config.check_cov,
            )
            # Sync CoV state back — cov_checker.previous_values was mutated
            # in-place by build_cov_payload; the reference is already shared
            # with PointListStore, so no explicit write-back needed.
            self.thread_dump['cov_responded'] = getstrTimeNow()

        if (
            cov_result is not None
            and self.config.notify_read_data == 'ONLY_COV'
        ):
            myprint('CoVNotification-->{}'.format(cov_result['CoVNotification']))
            self.thread_dump['cov_notified'] = getstrTimeNow()
            self.data_publisher.post(cov_result['CoVNotification'])

        if self.config.notify_read_data == 'ALL_RM':
            payload = self.data_publisher.build_all_data_payload(
                thread_id=self.thread_id,
                device_address=self.device_address,
                point_values=self.point_values,
                cov_checker=self.cov_checker,
                measured_time=measured_time,
                names_ready=self.names_ready,
            )
            self.data_publisher.post(payload)

        # ── DB write ─────────────────────────────────────────────────────
        if self.db_writer.connection_pool is not None and self.names_ready:

            heartbeat_due = self.cov_checker.is_heartbeat_due(
                self.device_address, measured_time
            )

            if heartbeat_due:
                # Heartbeat: write ALL current point values for a full periodic
                # snapshot.  This supersedes any CoV insert for this cycle —
                # every point will be written, so a separate CoV insert would
                # just create duplicates.
                insert_data = self.db_writer.build_insertion_data(
                    device_address=self.device_address,
                    point_values=self.point_values,
                    cov_checker=self.cov_checker,
                    data_time=measured_time,
                )
                if not insert_data:
                    printTrace('_post_process HEARTBEAT — no rows built for {}'.format(
                        self.device_address))
                if insert_data:
                    ok = self.db_writer.write(self.device_address, insert_data)
                    if ok:
                        self.cov_checker.mark_db_written(self.device_address, self.point_values.keys())
                        self.cov_checker.mark_heartbeat(self.device_address, measured_time)
                    else:
                        printTrace('_post_process HEARTBEAT write failed for {} — '
                                   'heartbeat NOT marked, will retry next cycle'.format(
                                       self.device_address))
                else:
                    # No data to write but still advance the heartbeat so we
                    # don't spin here every cycle with an empty point list.
                    self.cov_checker.mark_heartbeat(self.device_address, measured_time)

            elif cov_result is not None:
                # CoV insert — write only the changed points immediately.
                # Only runs when heartbeat is NOT due to avoid double-writing.
                cov_points = cov_result.get('CoVPoints') or self.point_values
                insert_data = self.db_writer.build_insertion_data(
                    device_address=self.device_address,
                    point_values=cov_points,
                    cov_checker=self.cov_checker,
                    data_time=measured_time,
                )
                if not insert_data:
                    printTrace('_post_process COV — no rows built for {} (check eqp_table_name)'.format(
                        self.device_address))
                if insert_data:
                    ok = self.db_writer.write(self.device_address, insert_data)
                    if ok:
                        self.cov_checker.mark_db_written(self.device_address, cov_points.keys())
                    else:
                        printTrace('_post_process COV write failed for {}'.format(
                            self.device_address))
