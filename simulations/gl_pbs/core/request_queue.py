"""
RequestQueue — thread-safe FIFO queue for HTTP→BACnet requests.

SRP: Only responsible for enqueuing and dequeuing request dicts.

Extracted from GLRequestQueue in bacnet_writer.py.
Removes the @bacpypes_debugging decorator dependency and the global
logger reference so this class has zero external coupling.
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RequestQueue:
    """
    FIFO queue of parsed HTTP request dicts.

    Each item shape:
        {
            "request_uuid": str,
            "request_parts": list[str],
            "query_params": dict,
            "post_body": dict,   # optional, POST requests only
        }
    """

    def __init__(self) -> None:
        self._queue: deque = deque()

    # ── public API ────────────────────────────────────────────────────────────

    def push(self, request: dict) -> None:
        """Enqueue a request dict."""
        self._queue.append(request)
        logger.debug(
            'RequestId: %s queued — pending: %d',
            request.get('request_uuid', '?'),
            len(self._queue),
        )

    def pull(self) -> Optional[dict]:
        """
        Dequeue and return the oldest request, or None if the queue is empty.
        """
        if not self._queue:
            return None
        request = self._queue.popleft()
        logger.info(
            'RequestId: %s — QUEUE_EXIT — pending: %d',
            request.get('request_uuid', '?'),
            len(self._queue),
        )
        return request

    def __len__(self) -> int:
        return len(self._queue)

    def __str__(self) -> str:
        return str(self._queue)
