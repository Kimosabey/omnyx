"""
ServerConfig — typed configuration for GLBACnetSolution HTTP-to-BACnet gateway.

SRP: Only holds configuration values; no behaviour.
Replaces the GL_DEFAULTS and GL_GLOBALS dicts.

Usage:
    from config.server_config import ServerConfig
    config = ServerConfig.from_args(args)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


# ── test URL templates ─────────────────────────────────────────────────────────
_DEFAULT_TEST_URLS: List[str] = [
    "http://localhost:7080/timesync/{}/8:3599",
    "http://localhost:7080/read/{}/2:13005/objectName",
    "http://localhost:7080/read/{}/2:13015/presentValue",
    "http://localhost:7080/readmultiple/{}/2:13025/objectName/description/presentValue"
    "/2:23012/objectName/description/20:23009/objectName/description"
    "/2:13006/objectName/description/presentValue/2:13018/objectName/description"
    "/20:1968/objectName/description",
    "http://localhost:7080/readrange/{}/20:1968/logBuffer/p%201%201",
    "http://localhost:7080/write/{}/2:13024/presentValue/256",
    "http://localhost:7080/discoverobjects/{}/8:3599",
    "http://localhost:7080/read/{}/8:3599/objectList",
]

# ── BACnet service name constants ──────────────────────────────────────────────
BACNET_SERVICES = {
    'DISCOVER_DEVICES': 'discoverdevices',
    'READ': 'read',
    'READ_MULTIPLE': 'readmultiple',
    'READ_RANGE': 'readrange',
    'SUBSCRIBE_COV': 'subscribe',
    'TIME_SYNC': 'timesync',
    'DISCOVER_OBJECTS': 'discoverobjects',
    'DISCOVER_OBJECTS_NO_SEGMENTATION': 'discoverobjects_nosegmentation',
    'WRITE': 'write',
    'WRITE_SCHEDULE': 'writeSchedule',
}


@dataclass
class ServerConfig:
    """
    Typed, immutable-at-runtime configuration for the BACnet gateway.

    Defaults mirror the original GL_DEFAULTS / GL_GLOBALS dicts.
    Runtime-mutable fields (my_ip_address, args) are Optional and set after
    network initialisation.
    """

    # HTTP server
    host: str = field(default_factory=lambda: os.getenv("HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", 7080)))

    # Response posting
    post_route: str = 'https://localhost:443/v1/devices/bacnetevents'

    # Queue
    q_process_interval_secs: float = 1.0

    # Network
    default_ip_address: str = '127.0.0.1'
    my_ip_address: str = ''

    # BACnet CoV subscription
    confirmed_subscription_cov: bool = True
    subscription_cov_lifetime: int = 0   # 0 = forever

    # Object Name Handler
    use_object_name_handler: bool = False

    # Test automation (set from CLI args)
    bacnet_test_device_ip: Optional[str] = None

    # Router references: list of (address_str, network_list)
    router_references: List = field(default_factory=list)

    # ── BACnet service names (constants) ──────────────────────────────────────
    @property
    def services(self) -> dict:
        return BACNET_SERVICES

    @property
    def test_urls(self) -> List[str]:
        return _DEFAULT_TEST_URLS

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_args(cls, args) -> 'ServerConfig':
        """
        Build a ServerConfig from the parsed ConfigArgumentParser namespace.
        ``args`` is the namespace returned by parser.parse_args().
        """
        cfg = cls()
        cfg.host = getattr(args, 'host', cfg.host)
        cfg.port = int(getattr(args, 'port', cfg.port))
        cfg.post_route = getattr(args, 'postroute', cfg.post_route)
        cfg.q_process_interval_secs = float(
            getattr(args, 'qProcessIntervalInSeconds', cfg.q_process_interval_secs)
        )
        cfg.default_ip_address = getattr(args, 'defaultIPAddress', cfg.default_ip_address)
        cfg.bacnet_test_device_ip = getattr(args, 'testBACnetIP', None)
        cfg.use_object_name_handler = getattr(args, 'useObjectNameHandler', False)

        return cfg
