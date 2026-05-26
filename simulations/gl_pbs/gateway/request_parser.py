"""
request_parser — converts raw HTTP paths into structured BACnet request dicts.

SRP: Only responsible for parsing; no queue pushing, no BACnet I/O.

Extracted from processHttpRequest() and parseHttpRequestforBACnet()
in bacnet_writer.py.  The request_queue is no longer touched here —
the caller (HttpRequestHandler) is responsible for enqueuing.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from collections import abc
from typing import Optional

try:
    from urlparse import urlparse, parse_qs        # Python 2
except ImportError:
    from urllib.parse import urlparse, parse_qs    # Python 3

from config.server_config import BACNET_SERVICES

logger = logging.getLogger(__name__)

# Address alias map (e.g. logical name → real IP:port)
CONTROLLER_MAP: dict = {"DDC10": "192.168.56.1:2001"}


# ── UUID helper ───────────────────────────────────────────────────────────────

def _get_request_uuid(query: dict) -> str:
    """
    Extract a v4 UUID from the parsed query string, or generate a fresh one.
    Port of getRequestUUID() in bacnet_writer.py.
    """
    if 'id' in query:
        raw = query['id']
        test_id = str(raw[0] if isinstance(raw, abc.Sequence) else raw)
        try:
            uuid.UUID(test_id, version=4)
            return test_id
        except ValueError:
            pass
    return str(uuid.uuid4())


# ── public API ────────────────────────────────────────────────────────────────

def parse_http_request(
    client_address: tuple = ('localhost', 'NA'),
    request_line: str = '',
    request_path: str = '',
    post_body=None,
) -> dict:
    """
    Parse an incoming HTTP GET/POST path into a structured request dict.

    Returns a dict with keys:
        request_uuid  : str
        request_parts : list[str]
        query_params  : dict
        post_body     : dict  (only for POST requests)
        Request_At    : str
        Arguments     : list[str]
        current_status: str

    Does NOT enqueue the request — the caller is responsible.

    Port of processHttpRequest() in bacnet_writer.py.
    """
    if not request_path:
        request_path = request_line

    parsed = urlparse(request_path)
    query = parse_qs(parsed.query)
    request_uuid = _get_request_uuid(query)
    args = parsed.path.split('/')

    logger.info(
        'Client %s — request: %s — uuid: %s — status: SERVER_RECEIVED',
        ':'.join(map(str, client_address)),
        request_path,
        request_uuid,
    )
    logger.debug('parse_http_request args: %r', args)

    result: dict = {
        'request_uuid': request_uuid,
        'request_parts': args,
        'query_params': query,
    }

    if post_body is not None:
        result['post_body'] = post_body

    from datetime import datetime
    result['Request_At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    result['Arguments'] = args
    result['current_status'] = 'Work in progress...'

    return result


def parse_for_bacnet(http_request: dict) -> Optional[dict]:
    """
    Convert a parsed HTTP request dict into BACnet service parameters.

    Returns a dict of service parameters, or None when the request cannot
    be mapped to a known BACnet service.

    Port of parseHttpRequestforBACnet() in bacnet_writer.py.
    Parameters are now passed explicitly instead of read from GL_GLOBALS.
    """
    parsed_params = None
    myreq = None

    try:
        if http_request is None:
            return None

        myreq = http_request.get('request_parts')
        if myreq is None or len(myreq) <= 3:
            return None

        logger.debug('parse_for_bacnet parts: %r', myreq)

        parsed_params = {}
        parsed_params['service'] = myreq[1]

        # segmentation flag
        if parsed_params['service'] == BACNET_SERVICES['DISCOVER_OBJECTS']:
            parsed_params['segmentationSupported'] = True
        elif parsed_params['service'] == BACNET_SERVICES['DISCOVER_OBJECTS_NO_SEGMENTATION']:
            parsed_params['service'] = BACNET_SERVICES['DISCOVER_OBJECTS']
            parsed_params['segmentationSupported'] = False

        # address / object-id
        parsed_params['objid'] = None
        raw_addr = str(myreq[2])
        parsed_params['destination'] = raw_addr

        # controller alias map
        if parsed_params['destination'] in CONTROLLER_MAP:
            parsed_params['destination'] = CONTROLLER_MAP[parsed_params['destination']]

        # object ID (for non-readmultiple services)
        if parsed_params['service'] == BACNET_SERVICES['READ_MULTIPLE']:
            parsed_params['objids_propids'] = '/' + '/'.join(myreq[3:])
        else:
            if parsed_params['objid'] is None:
                parsed_params['objid'] = myreq[3]

        # CoV subscription params
        if parsed_params['service'] == BACNET_SERVICES['SUBSCRIBE_COV']:
            parsed_params['confirmed'] = True   # defaults; overridden by config
            parsed_params['lifetime'] = 0

        # optional fields: propertyId, arrayindex, newValue, indexrange
        if len(myreq) > 4:
            parsed_params['propertyId'] = myreq[4]
            if len(myreq) > 5:
                svc = parsed_params['service']
                if svc == BACNET_SERVICES['READ']:
                    idx = int(myreq[5]) if myreq[5] != '0' else None
                    parsed_params['arrayindex'] = idx if idx else None
                elif svc == BACNET_SERVICES['WRITE']:
                    parsed_params['newValue'] = myreq[5]
                    parsed_params['arrayindex'] = None
                    parsed_params['priority'] = None
                    if len(myreq) > 6 and myreq[6] != '-':
                        parsed_params['arrayindex'] = int(myreq[6])
                    if len(myreq) > 7:
                        parsed_params['priority'] = int(myreq[7])
                elif svc == BACNET_SERVICES['READ_RANGE']:
                    parsed_params['indexrange'] = myreq[5]

    except Exception:
        exc_type, exc_val, _ = sys.exc_info()
        logger.error('parse_for_bacnet error: %s %s', exc_type, exc_val)

    finally:
        logger.info(
            'parse_for_bacnet — request: %s — parsed: %s',
            http_request, parsed_params,
        )

    return parsed_params
