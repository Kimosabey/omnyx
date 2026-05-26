"""
network_watchdog — Background thread that monitors a local IP address.

Polls ``is_local_ip(ip)`` every *check_interval* seconds (default 5).
Fires ``on_lost()`` once when the address disappears and ``on_restored()``
once when it comes back.  Both callbacks are optional.

Typical usage
-------------
    watchdog = NetworkWatchdog(
        ip_address='192.168.1.100',
        on_lost=lambda: stop(),          # stop the BACnet event loop
    )
    watchdog.start()
    run()                                # blocks until stop() is called
    watchdog.stop()
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from core.network_utils import is_local_ip

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 5.0  # seconds


class NetworkWatchdog:
    """
    Daemon thread that polls whether *ip_address* is still bound to a
    local interface every *check_interval* seconds.

    Parameters
    ----------
    ip_address     : IP to watch (e.g. ``'192.168.1.100'``).
    check_interval : Polling interval in seconds (default 5).
    on_lost        : Called once when the IP disappears.
    on_restored    : Called once when the IP reappears.
    """

    def __init__(
        self,
        ip_address: str,
        check_interval: float = _DEFAULT_INTERVAL,
        on_lost: Optional[Callable] = None,
        on_restored: Optional[Callable] = None,
    ) -> None:
        self.ip_address = ip_address
        self.check_interval = check_interval
        self.on_lost = on_lost
        self.on_restored = on_restored

        self._stop_event = threading.Event()
        self._network_up = True  # assume network is up at start
        self._thread = threading.Thread(
            target=self._run, name='NetworkWatchdog', daemon=True
        )

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        logger.info(
            'NetworkWatchdog started — watching %s every %.0fs',
            self.ip_address, self.check_interval,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the watchdog thread to exit on its next wake-up."""
        self._stop_event.set()

    # ── internal ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.wait(self.check_interval):
            try:
                currently_up = is_local_ip(self.ip_address)
            except Exception as exc:
                logger.warning('NetworkWatchdog — IP check error: %s', exc)
                continue

            if self._network_up and not currently_up:
                self._network_up = False
                logger.warning('NetworkWatchdog — IP %s lost', self.ip_address)
                if self.on_lost:
                    try:
                        self.on_lost()
                    except Exception:
                        logger.exception('NetworkWatchdog on_lost callback error')

            elif not self._network_up and currently_up:
                self._network_up = True
                logger.info('NetworkWatchdog — IP %s restored', self.ip_address)
                if self.on_restored:
                    try:
                        self.on_restored()
                    except Exception:
                        logger.exception('NetworkWatchdog on_restored callback error')
