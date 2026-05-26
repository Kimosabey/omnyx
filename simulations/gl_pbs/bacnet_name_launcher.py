#!/usr/bin/env python
"""
bacnet_name_launcher.py — auto-launch one BACnet simulator per DDC.

Reads defaultIPAddress and rpmRequestsFile from config/GLBACpypes.ini,
discovers every unique DDC ID in the CSV, assigns each a BACnet port and
web-UI port, then spawns one bacnet_name_simulator.py subprocess per DDC.

All child processes are killed when the launcher exits for any reason
(Ctrl+C, SIGTERM, window close, or normal exit).

Usage
-----
  python bacnet_name_launcher.py
      (reads IP and CSV from config/GLBACpypes.ini)

  python bacnet_name_launcher.py <ini_file>
  python bacnet_name_launcher.py <ini_file> <base_bacnet_port> <base_web_port>
  python bacnet_name_launcher.py <ini_file> <base_bacnet_port> <base_web_port> <ip>
  python bacnet_name_launcher.py <ini_file> <base_bacnet_port> <base_web_port> <ip> <csv_file>

Port assignment (sequential, in CSV first-appearance order):
  DDC at index i  →  BACnet port = base_bacnet_port + i
                      Web UI port = base_web_port   + i

Defaults (from config/GLBACpypes.ini)
--------------------------------------
  ip          defaultIPAddress
  csv_file    rpmRequestsFile
  base ports  BACnet=2001, Web=7091
"""
import atexit
import configparser
import csv
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)
logger = logging.getLogger('NameSimLauncher')

_SIMULATOR   = str(Path(__file__).with_name('bacnet_name_simulator.py'))
_DEFAULT_INI = 'config/GLBACpypes.ini'

# ── INI helpers ────────────────────────────────────────────────────────────────

def read_ini(ini_file: str) -> dict:
    """Return {'ip': str|None, 'csv_file': str} from GLBACpypes.ini."""
    result = {'ip': None, 'csv_file': 'data/eqp_name_handling.csv'}
    try:
        c = configparser.ConfigParser()
        c.read(ini_file)
        if 'BACpypes' not in c:
            logger.warning('read_ini: [BACpypes] section missing in %s', ini_file)
            return result
        sec = c['BACpypes']
        ip = sec.get('defaultIPAddress', '').strip()
        if ip:
            result['ip'] = ip
        csv_path = sec.get('rpmRequestsFile', '').strip()
        if csv_path:
            result['csv_file'] = csv_path
        logger.info('INI %s → ip=%s  csv=%s', ini_file, result['ip'], result['csv_file'])
    except Exception:
        logger.exception('read_ini: error reading %s', ini_file)
    return result


def write_controllermap(
    ini_file: str,
    assignments: 'List[Tuple[str, int, int]]',
    ip: str,
) -> None:
    """
    Write/update the controllermap key in ini_file.

    Builds {"DDC01": "ip:2001", "DDC02": "ip:2002", ...} from assignments
    and replaces the existing uncommented controllermap= line in-place,
    preserving all comments and other settings.
    If no uncommented controllermap line exists, appends one.
    """
    import json as _json
    import re as _re

    cmap = {ddc_id: '{}:{}'.format(ip, bacnet_port)
            for ddc_id, bacnet_port, _ in assignments}
    new_line = 'controllermap={}\n'.format(_json.dumps(cmap, separators=(',', ': ')))

    try:
        with open(ini_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Replace the first uncommented controllermap= line
        pattern = _re.compile(r'^\s*controllermap\s*=', _re.IGNORECASE)
        replaced = False
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = new_line
                replaced = True
                break

        if not replaced:
            lines.append(new_line)

        with open(ini_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        logger.info('controllermap written to %s: %s', ini_file, cmap)
    except Exception:
        logger.exception('write_controllermap: failed to update %s', ini_file)

# ── CSV helpers ────────────────────────────────────────────────────────────────

def read_ddc_ids(csv_file: str) -> List[str]:
    """Return unique DDC IDs in first-appearance order, skipping flagged rows."""
    seen: List[str] = []
    seen_set: set = set()
    try:
        with open(csv_file, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for line in reader:
                if not line:
                    continue
                ddc_id    = line[0].strip().upper() if len(line) > 0 else ''
                skip_flag = line[7].strip()         if len(line) > 7 else ''
                if ddc_id and ddc_id not in seen_set and not skip_flag:
                    seen.append(ddc_id)
                    seen_set.add(ddc_id)
    except Exception:
        logger.exception('read_ddc_ids: cannot read %s', csv_file)
    return seen


def assign_ports(
    ddc_ids: List[str],
    base_bacnet: int,
    base_web: int,
) -> List[Tuple[str, int, int]]:
    """Return [(ddc_id, bacnet_port, web_port), ...] in CSV order."""
    return [
        (ddc_id, base_bacnet + i, base_web + i)
        for i, ddc_id in enumerate(ddc_ids)
    ]

# ── process group ──────────────────────────────────────────────────────────────

class SimulatorGroup:
    """Manages a set of bacnet_name_simulator subprocesses."""

    def __init__(self) -> None:
        self._procs: Dict[str, subprocess.Popen] = {}

    def launch_all(
        self,
        assignments: List[Tuple[str, int, int]],
        csv_file: str,
        ip: Optional[str],
    ) -> None:
        for ddc_id, bacnet_port, web_port in assignments:
            cmd = [sys.executable, _SIMULATOR,
                   ddc_id, str(bacnet_port), str(web_port)]
            if ip:
                cmd.append(ip)
            cmd.append(csv_file)
            cmd.append('--no-console')

            logger.info(
                'Starting %-12s  BACnet=%-6d  Web=http://%s:%d',
                ddc_id, bacnet_port, ip or '0.0.0.0', web_port,
            )
            self._procs[ddc_id] = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)

    def wait_all(self) -> None:
        """Block until every subprocess exits, or Ctrl+C is received."""
        try:
            while True:
                time.sleep(2)
                if all(p.poll() is not None for p in self._procs.values()):
                    logger.info('All simulators have exited.')
                    break
                for ddc_id, proc in list(self._procs.items()):
                    rc = proc.poll()
                    if rc is not None and rc != 0:
                        logger.warning('%s exited with code %d', ddc_id, rc)
        except KeyboardInterrupt:
            logger.info('Ctrl+C — stopping all simulators ...')
            # atexit will call stop_all

    def stop_all(self) -> None:
        """Terminate then force-kill all child simulators."""
        for ddc_id, proc in self._procs.items():
            if proc.poll() is None:
                logger.info('  Terminating %s (pid=%d)', ddc_id, proc.pid)
                proc.terminate()
        time.sleep(3)
        for ddc_id, proc in self._procs.items():
            if proc.poll() is None:
                logger.warning('  Force-killing %s (pid=%d)', ddc_id, proc.pid)
                proc.kill()

# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print('Graylinx BACnet Name-Handler Simulator Launcher')

    # ── parse CLI ──────────────────────────────────────────────────────────────
    ini_file    = sys.argv[1] if len(sys.argv) >= 2 else _DEFAULT_INI
    base_bacnet = int(sys.argv[2]) if len(sys.argv) >= 3 else 2001
    base_web    = int(sys.argv[3]) if len(sys.argv) >= 4 else 7091
    cli_ip      = sys.argv[4] if len(sys.argv) >= 5 else None
    cli_csv     = sys.argv[5] if len(sys.argv) >= 6 else None

    # ── read INI ───────────────────────────────────────────────────────────────
    ini      = read_ini(ini_file)
    ip       = cli_ip  or ini['ip']        # CLI overrides INI
    csv_file = cli_csv or ini['csv_file']  # CLI overrides INI

    # ── discover DDC IDs ───────────────────────────────────────────────────────
    ddc_ids = read_ddc_ids(csv_file)
    if not ddc_ids:
        logger.error('No DDC IDs found in %s — nothing to launch.', csv_file)
        sys.exit(1)

    assignments = assign_ports(ddc_ids, base_bacnet, base_web)

    # ── update controllermap in INI ────────────────────────────────────────────
    if ip:
        write_controllermap(ini_file, assignments, ip)
    else:
        logger.warning('No IP resolved — skipping controllermap update.')

    # ── print assignment table ─────────────────────────────────────────────────
    ip_label = ip or '(auto-detect)'
    print()
    print('  IP: {}'.format(ip_label))
    print()
    print('  {:<14}  {:>12}  {:>10}'.format('DDC', 'BACnet port', 'Web port'))
    print('  ' + '-' * 42)
    for ddc_id, bacnet_port, web_port in assignments:
        print('  {:<14}  {:>12}  {:>10}'.format(ddc_id, bacnet_port, web_port))
    print()

    # ── register cleanup for ALL exit paths ───────────────────────────────────
    # (Ctrl+C, sys.exit, SIGTERM from task manager / process manager)
    group = SimulatorGroup()
    atexit.register(group.stop_all)

    def _on_signal(*_):
        sys.exit(0)           # triggers atexit

    signal.signal(signal.SIGTERM, _on_signal)
    if hasattr(signal, 'SIGBREAK'):   # Windows Ctrl+Break
        signal.signal(signal.SIGBREAK, _on_signal)

    # ── launch ─────────────────────────────────────────────────────────────────
    group.launch_all(assignments, csv_file, ip)
    group.wait_all()


if __name__ == '__main__':
    main()
