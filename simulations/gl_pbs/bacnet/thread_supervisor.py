"""
ThreadSupervisor — manages thread lifecycle and retry logic.

SRP: Only responsible for starting threads, waiting for completion,
     collecting failures, and retrying with doubled timeouts.

Refactored from ThreadSupervisor in the original bacnet_reader.py.
Global state mutations (gl_point_list write-back, names_ready flag) are
replaced with PointListStore method calls.
"""
from __future__ import annotations

from threading import Event, Thread
from typing import TYPE_CHECKING, Callable, List, Optional

from glDASLibrary import mythread_dump, myprint, printTrace, prepareEquipmentParameterDataFile

if TYPE_CHECKING:
    from bacnet.read_thread import ReadPointListThread
    from config.app_config import AppConfig
    from core.point_list_store import PointListStore

SUCCESS = 0


class ThreadSupervisor(Thread):
    """
    Runs a list of ReadPointListThreads with automatic retry on failure.

    After each batch:
      - Successful threads write their CoV state back via PointListStore
      - Failed threads are cloned with doubled timeout for the next attempt
      - The names_ready flag is set after the first completed attempt

    Sets completion_event when done (used for callbacks and testing).
    """

    def __init__(
        self,
        thread_list: List['ReadPointListThread'],
        point_list_store: 'PointListStore',
        config: 'AppConfig',
        max_attempts: int = 3,
        completion_event: Optional[Event] = None,
        post_complete_callback: Optional[Callable] = None,
    ) -> None:
        super().__init__()
        self.thread_list = thread_list
        self.store = point_list_store
        self.config = config
        self.max_attempts = max_attempts
        self.completion_event = completion_event or Event()
        self.post_complete_callback = post_complete_callback

    # ── Thread API ────────────────────────────────────────────────────────

    def run(self) -> None:
        current_list = self.thread_list
        total_success = 0  # cumulative across all retry attempts

        for attempt in range(self.max_attempts):
            # Start all threads in this attempt
            for t in current_list:
                t.start()
            for t in current_list:
                t.join()

            error_list: List['ReadPointListThread'] = []
            attempt_success = 0

            for t in current_list:
                if t.attempt_status == SUCCESS:
                    attempt_success += 1
                    total_success += 1

                    # post-process here when CoV is NOT computed within the thread
                    if not self.config.cov_computation_within_thread:
                        t._post_process()

                    # Persist CoV state for this device
                    self.store.save_previous_values(
                        t.list_index, t.cov_checker.previous_values
                    )
                else:
                    error_list.append(t.clone(t.timeout * 2, attempt + 1))

            printTrace(
                'Status - Errored:{} Attempt:{} AttemptSuccess:{} TotalSuccess:{} of {}'.format(
                    len(error_list),
                    attempt,
                    attempt_success,
                    total_success,
                    len(self.thread_list),
                )
            )

            # Log timing data
            self._write_thread_dump(current_list, attempt)

            # After the first pass names are resolved
            self.store.mark_names_ready()

            if error_list:
                current_list = error_list
            else:
                break

        # Optional one-shot callback (e.g. write equipment parameter file)
        if self.post_complete_callback is not None:
            self.post_complete_callback()

        self.completion_event.set()

    # ── thread dump ───────────────────────────────────────────────────────

    def _write_thread_dump(
        self,
        thread_list: List['ReadPointListThread'],
        attempt: int,
    ) -> None:
        """Port of ThreadSupervisor.prepareThreadDump()."""
        params = [
            'initiated', 'started', 'device_requested',
            'device_responded', 'device_errored',
            'cov_requested', 'cov_responded', 'cov_notified',
        ]
        header = 'uuid,attempt,device_address,{}\n'.format(','.join(params))
        rows = '\n'.join([
            t.get_thread_dump(params, prefix=str(attempt))
            for t in thread_list
        ])
        dump_content = header + rows + '\n-'

        dump_file = (
            self.config.thread_dump_file_prefix
            + self.config.rpm_requests_file
        )
        myprint(dump_file)
        mythread_dump(dump_content, fileName=dump_file)
