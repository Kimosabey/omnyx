#!/usr/bin/env python
"""
ddc_watchdog.py — Monitors DDC IP addresses and restarts Windows services on network recovery.

Behaviour
---------
- Reads DDC controller IPs automatically from controllermap in GLBACpypes.ini.
- Pings all valid IPv4 DDC addresses every 5 seconds (MSTP addresses are skipped).
- If ALL pingable DDC IPs time out simultaneously, the network is considered DOWN.
- Waits until at least one DDC IP responds again (network recovered).
- Restarts two configured Windows services via PowerShell.

Configuration
-------------
  DEFAULT_INI  — path to the BACpypes ini file (contains controllermap)
  SERVICES     — Windows service names to restart on recovery
  PING_INTERVAL — seconds between each ping round (default 5)

Usage
-----
    python ddc_watchdog.py
    python ddc_watchdog.py --ini config/GLBACpypes.ini
    python ddc_watchdog.py --ips 192.168.1.10 192.168.1.11   # manual override
    python ddc_watchdog.py --services MySvc1 MySvc2
"""
from __future__ import annotations

import argparse
import configparser
import ipaddress
import json
import logging
import os
import subprocess
import sys
import time
from typing import List

# ── Configuration — edit these for your site ──────────────────────────────────

DEFAULT_INI: str = "config/GLBACpypes.ini"   # path to the BACpypes ini file

SERVICES: List[str] = [
    "gl_pbs1",
    "gl_pbs2",
]

PING_INTERVAL: float = 5.0        # seconds between each ping round
PING_TIMEOUT_MS: int = 1000       # milliseconds for a single ping to time out

# Must match HEARTBEAT_FILE in bacnet_reader.py
HEARTBEAT_FILE: str = "heartbeat.txt"
HEARTBEAT_TIMEOUT_SECS: float = 60.0   # reader considered hung after this long

# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ddc_watchdog.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("ddc_watchdog")


def load_ips_from_ini(ini_path: str) -> List[str]:
    """Parse *ini_path* and return all host IPs found in the controllermap key.

    The controllermap value is a JSON object like:
        {"DDC08": "192.168.1.125:2001", "DDC09": "5:1"}
    The host part (before the optional colon) is extracted for each entry.
    """
    if not os.path.isfile(ini_path):
        log.warning("INI file not found: %s — no IPs loaded from file.", ini_path)
        return []

    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding="utf-8")

    # configparser requires a section; BACpypes ini uses [BACpypes]
    raw = None
    for section in parser.sections():
        if parser.has_option(section, "controllermap"):
            raw = parser.get(section, "controllermap")
            break

    if raw is None:
        log.warning("No 'controllermap' key found in %s.", ini_path)
        return []

    try:
        controller_map: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Could not parse controllermap JSON from %s: %s", ini_path, exc)
        return []

    ips = []
    for ddc_name, addr in controller_map.items():
        host = addr.split(":")[0]   # strip optional port
        log.info("  INI controllermap  %-10s  ->  %s", ddc_name, addr)
        ips.append(host)

    return ips


def is_valid_ipv4(address: str) -> bool:
    """Return True if *address* (optionally with :port) is a valid IPv4 address.

    MSTP addresses such as '5:1' (network:node) or bare integers are not valid
    IPv4 addresses and will return False.
    """
    host = address.split(":")[0]   # strip optional port
    try:
        ipaddress.IPv4Address(host)
        return True
    except ipaddress.AddressValueError:
        return False


def filter_pingable_ips(ips: List[str]) -> List[str]:
    """Return only the entries from *ips* that are valid IPv4 addresses.

    Entries that look like MSTP addresses (e.g. '5:1') are logged and dropped.
    """
    pingable = []
    for addr in ips:
        if is_valid_ipv4(addr):
            pingable.append(addr)
        else:
            log.info("Skipping non-IP (MSTP) address: %s", addr)
    return pingable


def heartbeat_is_fresh(
    path: str = HEARTBEAT_FILE,
    timeout_secs: float = HEARTBEAT_TIMEOUT_SECS,
) -> bool:
    """Return True if the heartbeat file exists and was written within *timeout_secs*.

    Returns False if the file is missing (reader never started) or stale.
    """
    try:
        age = time.time() - os.path.getmtime(path)
        return age < timeout_secs
    except OSError:
        return False   # file missing


def ping_ip(ip: str, timeout_ms: int = PING_TIMEOUT_MS) -> bool:
    """Return True if *ip* responds to a single ICMP ping within *timeout_ms*."""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=(timeout_ms / 1000) + 2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def all_ddcs_unreachable(ips: List[str]) -> bool:
    """Return True only when every DDC IP fails to respond."""
    results = {ip: ping_ip(ip) for ip in ips}
    for ip, reachable in results.items():
        status = "OK" if reachable else "TIMEOUT"
        log.debug("  %-20s %s", ip, status)
    return not any(results.values())


def any_ddc_reachable(ips: List[str]) -> bool:
    """Return True as soon as any DDC IP responds."""
    return any(ping_ip(ip) for ip in ips)


def restart_service(service_name: str) -> bool:
    """Restart a Windows service with elevation via PowerShell. Returns True on success.

    Uses sc.exe stop/start so it works even when the calling process is not
    running as Administrator — sc.exe requests the required privilege directly
    from the Service Control Manager.
    """
    log.info("Restarting service: %s", service_name)
    try:
        for action in ("stop", "start"):
            result = subprocess.run(
                ["sc.exe", action, service_name],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # sc.exe returns 0 on success; 1062 on stop means already stopped (OK for stop)
            already_stopped = (action == "stop" and result.returncode == 1062)
            if result.returncode != 0 and not already_stopped:
                log.error(
                    "  sc.exe %s '%s' failed (exit %d): %s",
                    action,
                    service_name,
                    result.returncode,
                    (result.stdout + result.stderr).strip(),
                )
                return False
            log.info("  sc.exe %s '%s' OK.", action, service_name)

        log.info("  Service '%s' restarted successfully.", service_name)
        return True
    except subprocess.TimeoutExpired:
        log.error("  Timed out restarting service '%s'.", service_name)
        return False
    except FileNotFoundError:
        log.error("  sc.exe not found. Cannot restart services.")
        return False


def restart_all_services(services: List[str]) -> None:
    for svc in services:
        restart_service(svc)


def run_watchdog(ips: List[str], services: List[str]) -> None:
    log.info("DDC Watchdog started.")
    log.info("Services          : %s", ", ".join(services))
    log.info("Ping interval     : %.0f s", PING_INTERVAL)
    log.info("Heartbeat timeout : %.0f s", HEARTBEAT_TIMEOUT_SECS)
    log.info("Heartbeat file    : %s", HEARTBEAT_FILE)

    ips = filter_pingable_ips(ips)
    if not ips:
        log.error("No pingable IP addresses remain after filtering. Exiting.")
        sys.exit(1)
    log.info("Monitoring IPs    : %s", ", ".join(ips))

    while True:
        time.sleep(PING_INTERVAL)

        if heartbeat_is_fresh():
            # Reader is alive — nothing to do
            log.debug("Heartbeat OK.")
            continue

        # ── Heartbeat stale (or file missing) — start DDC ping ────────────
        log.warning(
            "Heartbeat not received for > %.0f s — pinging DDC IPs...",
            HEARTBEAT_TIMEOUT_SECS,
        )

        if any_ddc_reachable(ips):
            # Network is fine but reader stopped sending heartbeat → hung reader
            log.warning(
                "DDC reachable but heartbeat stale — reader is HUNG. Restarting services."
            )
            restart_all_services(services)

        else:
            # Network is also down
            log.warning("ALL DDC IPs unreachable — network is DOWN.")
            log.info("Waiting for network recovery...")
            while not any_ddc_reachable(ips):
                time.sleep(PING_INTERVAL)
            log.info("Network RECOVERED — DDC(s) responding again. Restarting services.")
            restart_all_services(services)

        # After restarting, give the services a moment before checking heartbeat again
        log.info("Waiting 15 s for services to come back up...")
        time.sleep(15)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ping DDC IPs and restart Windows services on network recovery."
    )
    parser.add_argument(
        "--ini",
        default=DEFAULT_INI,
        metavar="FILE",
        help=f"BACpypes INI file to read controllermap from (default: {DEFAULT_INI}).",
    )
    parser.add_argument(
        "--ips",
        nargs="+",
        default=None,
        metavar="IP",
        help="DDC IP addresses to monitor — overrides controllermap from INI.",
    )
    parser.add_argument(
        "--services",
        nargs="+",
        default=None,
        metavar="SVC",
        help="Windows service names to restart (overrides SERVICES constant).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=PING_INTERVAL,
        metavar="SECS",
        help=f"Ping interval in seconds (default {PING_INTERVAL}).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    PING_INTERVAL = args.interval

    # IP source priority: --ips console arg > controllermap in ini file
    if args.ips:
        ips = args.ips
        log.info("Using IPs from command line: %s", ", ".join(ips))
    else:
        log.info("Loading DDC IPs from INI: %s", args.ini)
        ips = load_ips_from_ini(args.ini)

    services = args.services if args.services else SERVICES

    if not ips:
        log.error(
            "No DDC IPs found. Check controllermap in %s or pass --ips.", args.ini
        )
        sys.exit(1)
    if not services:
        log.error("No services configured. Edit SERVICES or use --services.")
        sys.exit(1)

    try:
        run_watchdog(ips, services)
    except KeyboardInterrupt:
        log.info("DDC Watchdog stopped by user.")
