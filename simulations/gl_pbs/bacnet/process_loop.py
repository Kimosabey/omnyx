"""
process_loop — recurring BACnet queue dispatcher.

SRP: Polls the RequestQueue on a fixed interval, checks network health,
     and dispatches to the injected BACnetServicesApplication.

DIP: All dependencies (queue, application, config, network checker) are
     injected at construction — no global variables.

Extracted from GLProcessLoop in bacnet_writer.py.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from bacpypes.core import deferred
from bacpypes.task import RecurringTask

from config.server_config import BACNET_SERVICES
from core.network_utils import get_local_ip_address
from gateway.request_parser import parse_for_bacnet

if TYPE_CHECKING:
    from bacnet.application import BACnetServicesApplication
    from config.server_config import ServerConfig
    from core.request_queue import RequestQueue

logger = logging.getLogger(__name__)


class ProcessLoop(RecurringTask):
    """
    Runs at a fixed interval to:
      1. Check network health; stop/restart BACnet on IP change.
      2. Pull the next request from the queue and dispatch it to the
         appropriate service on BACnetServicesApplication.

    Port of GLProcessLoop with all global references removed.
    """

    def __init__(
        self,
        interval_ms: float,
        request_queue: 'RequestQueue',
        config: 'ServerConfig',
        start_bacnet: Optional[Callable] = None,
        stop_bacnet: Optional[Callable] = None,
    ) -> None:
        """
        Parameters
        ----------
        interval_ms   : RecurringTask period in milliseconds.
        request_queue : The application-level request queue.
        config        : ServerConfig (used for default_ip_address).
        start_bacnet  : Callable() to call when the network comes back up.
        stop_bacnet   : Callable() to call when the network goes down.
        """
        super().__init__(interval_ms)
        self.install_task()

        self._queue = request_queue
        self._config = config
        self._start_bacnet = start_bacnet
        self._stop_bacnet = stop_bacnet

        # Injected after the BACnet application is created (see main())
        self._application: Optional['BACnetServicesApplication'] = None

        self._network_was_down: bool = False
        self._network_status: Optional[str] = None
        self._check_network()

    # ── post-construction wiring ───────────────────────────────────────────────

    def set_application(self, app: 'BACnetServicesApplication') -> None:
        """Wire the BACnet application after it is created."""
        self._application = app

    # ── RecurringTask API ──────────────────────────────────────────────────────

    def process_task(self) -> None:
        logger.debug('ProcessLoop.process_task')
        self._check_network()
        if self._network_status is not None:
            self._dispatch_next()

    # ── network health ─────────────────────────────────────────────────────────

    def _check_network(self) -> None:
        self._network_status = get_local_ip_address(
            default_ip=self._config.default_ip_address,
            use_ethernet=True,
        )
        logger.debug('Network status: %s (expected: %s)',
                     self._network_status, self._config.my_ip_address)

        current_ip_matches = (
            self._network_status is not None
            and self._network_status == self._config.my_ip_address
        )

        if not current_ip_matches:
            if not self._network_was_down:
                logger.error(
                    'Network down — got %s expected %s — stopping BACnet',
                    self._network_status, self._config.my_ip_address,
                )
                self._network_was_down = True
                if self._stop_bacnet:
                    self._stop_bacnet()
        else:
            if self._network_was_down:
                logger.info('Network restored: %s — restarting BACnet', self._network_status)
                self._network_was_down = False
                if self._start_bacnet:
                    self._start_bacnet()

    # ── request dispatch ───────────────────────────────────────────────────────

    def _dispatch_next(self) -> None:
        """
        Pull one request from the queue, parse it, and dispatch to the
        appropriate service on self._application.

        Port of processNextQueuedRequest() in bacnet_writer.py.
        """
        raw = self._queue.pull()
        if raw is None:
            return

        parsed = parse_for_bacnet(raw)
        if parsed is None or 'service' not in parsed:
            logger.debug('_dispatch_next — no parsed service, skipping')
            return

        app = self._application
        if app is None:
            logger.warning('_dispatch_next — application not set, dropping request')
            return

        svc = parsed['service']
        logger.info('Dispatching service: %s — request_uuid: %s', svc, raw.get('request_uuid'))

        if svc == BACNET_SERVICES['DISCOVER_DEVICES']:
            deferred(app.discoverDevices, raw, parsed)

        elif svc == BACNET_SERVICES['DISCOVER_OBJECTS']:
            deferred(app.discoverObjects, raw, parsed, parsed.get('segmentationSupported', True))

        elif svc == BACNET_SERVICES['DISCOVER_OBJECTS_NO_SEGMENTATION']:
            deferred(app.discoverObjects, raw, parsed, False)

        elif svc == BACNET_SERVICES['READ']:
            self.suspend_task()
            deferred(app.readObjectProperty, raw, parsed)

        elif svc == BACNET_SERVICES['READ_MULTIPLE']:
            self.suspend_task()
            deferred(app.readMultipleProperties, raw, parsed)

        elif svc == BACNET_SERVICES['SUBSCRIBE_COV']:
            self.suspend_task()
            deferred(app.subscribePropertyCoV, raw, parsed)

        elif svc == BACNET_SERVICES['READ_RANGE']:
            self.suspend_task()
            deferred(app.trendLogReadRange, raw, parsed)

        elif svc == BACNET_SERVICES['TIME_SYNC']:
            deferred(app.timeSyncDevice, raw, parsed)

        elif svc in (BACNET_SERVICES['WRITE'], BACNET_SERVICES['WRITE_SCHEDULE']):
            self.suspend_task()
            deferred(app.writeObjectProperty, raw, parsed)

        else:
            logger.error('Unknown service %r — request dropped', svc)

    # ── callback used by application service completions ──────────────────────

    def resume_and_dispatch(self) -> None:
        """
        Called by BACnetServicesApplication service callbacks to resume the
        loop and immediately process the next queued request.

        Port of the pattern:
            GL_GLOBALS['appQueueProcessor'].resume_task()
            processNextQueuedRequest()
        """
        self.resume_task()
        self._dispatch_next()
