"""
network_utils — IP address detection utilities.

SRP: Only responsible for discovering the local IP address.

Extracted and consolidated from the three getLocalIPAddress* variants
(getLocalIPAddress_wifi, getLocalIPAddress_eth, getLocalIPAddress) in
bacnet_writer.py.  All three used the same underlying logic; this
module exposes a single public function.
"""
from __future__ import annotations

import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)


# ── private helpers ────────────────────────────────────────────────────────────

def _get_all_unix_ips() -> list:
    """Return all IPv4/IPv6 addresses on POSIX systems via netifaces."""
    try:
        import netifaces  # type: ignore
        ips = set()
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            for family in (netifaces.AF_INET, netifaces.AF_INET6):
                for addr in addrs.get(family, []):
                    ips.add(addr['addr'])
        return sorted(ips)
    except ImportError:
        logger.warning('netifaces not installed; falling back to socket detection')
        return None  # signals caller to use bind-check instead


def _check_ethernet_ip(address: str) -> str:
    """
    Verify that *address* is actually assigned to a local interface.
    Returns *address* if found, '127.0.0.1' otherwise.
    """
    platform = os.name
    try:
        if platform == 'posix':
            ips = _get_all_unix_ips()
            if ips is None:
                # netifaces unavailable — try binding to the address directly
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.bind((address, 0))
                    s.close()
                    return address
                except OSError:
                    return '127.0.0.1'
            return address if address in ips else '127.0.0.1'
        else:  # 'nt' (Windows)
            ipv4_list = [
                a for a in socket.gethostbyname_ex(socket.gethostname())[2]
                if ':' not in a
            ]
            return address if address in ipv4_list else '127.0.0.1'
    except Exception as exc:
        logger.error('_check_ethernet_ip error: %s', exc)
        return '127.0.0.1'


# ── public API ─────────────────────────────────────────────────────────────────

def is_local_ip(address: str) -> bool:
    """Return True if *address* is assigned to a local network interface."""
    if not address or address == '127.0.0.1':
        return True
    return _check_ethernet_ip(address) == address


def get_local_ip_address(
    default_ip: str = '127.0.0.1',
    use_ethernet: bool = True,
    auto_detect: bool = True,
) -> Optional[str]:
    """
    Determine the local IP address to use for BACnet.

    Priority order
    --------------
    1. ``use_ethernet=True``  → validate *default_ip* against local interfaces.
    2. ``auto_detect=True``   → route-socket trick (connects to 10.254.254.254:1,
                                reads the local socket address).
    3. Fallback               → return *default_ip* unchanged.

    Returns None only when auto-detection fails entirely.
    """
    # If an explicit non-loopback IP is provided, trust it directly without
    # validation — the caller knows which interface to bind to.
    if default_ip and default_ip != '127.0.0.1':
        logger.debug('get_local_ip_address (explicit) → %s', default_ip)
        return default_ip

    if use_ethernet:
        ip = _check_ethernet_ip(default_ip)
        logger.debug('get_local_ip_address (ethernet) → %s', ip)
        return ip

    if auto_detect:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.254.254.254', 1))
            ip = s.getsockname()[0]
            s.close()
            logger.debug('get_local_ip_address (auto-detect) → %s', ip)
            return ip
        except Exception as exc:
            logger.error('get_local_ip_address auto-detect failed: %s', exc)
            return None

    logger.debug('get_local_ip_address (default) → %s', default_ip)
    return default_ip
