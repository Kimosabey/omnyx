"""
ResponsePoster — sends JSON payloads to the configured HTTP POST endpoint.

SRP: Only responsible for serialising a response dict and posting it via
     requests.post().

Extracted from postResponseUsingRequests() in bacnet_writer.py.
The post_route is injected at construction so there are no global references.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ResponsePoster:
    """
    Posts BACnet service response payloads to an HTTP endpoint.

    Parameters
    ----------
    post_route : str
        Full URL to POST responses to.
    timeout : float
        Default request timeout in seconds.
    """

    def __init__(self, post_route: str, timeout: float = 2.50) -> None:
        self.post_route = post_route
        self.timeout = timeout

    # ── public API ────────────────────────────────────────────────────────────

    def post(
        self,
        body: dict,
        donotpost: bool = False,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Serialise *body* and POST it to self.post_route.

        Parameters
        ----------
        body : dict
            The payload to send as JSON.
        donotpost : bool
            When True the post is skipped (useful for testing/dry-run).
        timeout : float | None
            Override the instance-level timeout for this call.
        """
        logger.info('ResponsePoster.post — body: %s', body)

        if donotpost:
            logger.debug('ResponsePoster.post — donotpost=True, skipping')
            return

        # Strip non-serializable internal keys (prefixed with '_') from the
        # request sub-dict before JSON serialisation.  Keys like _status_callback
        # and _response_event are added by do_GET for internal use only.
        if body.get('request'):
            body = dict(body)
            body['request'] = {k: v for k, v in body['request'].items() if not k.startswith('_')}

        post_json = json.loads(json.dumps(body))
        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            response = requests.post(
                url=self.post_route,
                json=post_json,
                verify=False,
                timeout=effective_timeout,
            )
            logger.info(
                'ResponsePoster — status: %d body: %s',
                response.status_code,
                response.text,
            )
        except requests.exceptions.Timeout:
            logger.error('ResponsePoster — timeout posting to %s', self.post_route)
        except requests.exceptions.TooManyRedirects:
            logger.error('ResponsePoster — too many redirects for %s', self.post_route)
        except requests.exceptions.RequestException as exc:
            logger.error('ResponsePoster — error posting to %s: %s', self.post_route, exc)
