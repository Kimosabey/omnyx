#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
plant_snapshot.py

Builds a Plant_Snapshot JSON that matches the standard structure but with
LIVE BACnet present values instead of the last DB-committed values.

Strategy
--------
  1. Query the MySQL database (bac_test) with the same SQL used by
     plant_snapshot.js to get the exact device/point structure:
       ssType, device_id, ddcid, Equipment_Group, glSSId, name,
       objId, objName, param_id (p_name key)

  2. Fetch the live snapshot HTML from bacnet_reader.py web server
     (http://localhost:8624) and build a lookup:
       gl_code  →  { presentValue, measured_time }

  3. For every point in the DB structure, replace presentValue and
     measured_time with the live reader values (when available).

Output format matches plantsnapshot_mod.json exactly:
  {
    "Plant_Snapshot": {
      "<ssType>": {
        "<device_id>": {
          "ssType"            : "NONGL_SS_COMMON_HEADER",
          "ddcid"             : "<ddc_uuid>",
          "Equipment_Group"   : "Combination-1",
          "BACnetDeviceAddress": null,
          "glSSId"            : "010001c00000",
          "id"                : "<device_uuid>",
          "name"              : "01",
          "Eqp_Attributes": {
            "CWH_RT": {
              "objId"        : "0:13003",
              "objName"      : "GL 01 00 01 c0 0 002",
              "presentValue" : "9.48",        <- LIVE from reader
              "priority"     : [null * 16],
              "measured_time": "2025-11-26 19:32:39"  <- LIVE timestamp
            }
          }
        }
      }
    }
  }

Usage
-----
    "C:\\Users\\santhosh sekar\\Envs\\pbs\\Scripts\\python.exe" plant_snapshot.py
    "C:\\Users\\santhosh sekar\\Envs\\pbs\\Scripts\\python.exe" plant_snapshot.py --out -
    "C:\\Users\\santhosh sekar\\Envs\\pbs\\Scripts\\python.exe" plant_snapshot.py --reader-port 8624

Configuration
-------------
  DB settings read from config/GLBACpypes.ini  (db_host, db_user, db_password, db_name)
  Reader port from GLBACpypes.ini              (PBS2Webport)
  Both can be overridden via CLI flags.
"""
from __future__ import annotations

import argparse
import configparser
import json
import sys
from typing import Dict, List, Optional, Tuple

try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, URLError    # type: ignore

import mysql.connector  # type: ignore  # installed in project venv: pbs

# ── defaults (overridden by GLBACpypes.ini) ───────────────────────────────────

DEFAULT_INI          = "config/GLBACpypes.ini"
DEFAULT_DB_HOST      = "localhost"
DEFAULT_DB_USER      = "root"
DEFAULT_DB_PASSWORD  = ""
DEFAULT_DB_NAME      = "bac_test"
DEFAULT_READER_HOST  = "localhost"
DEFAULT_READER_PORT  = 8624
DEFAULT_OUT          = "plant_snapshot.json"

# ── INI loader ────────────────────────────────────────────────────────────────

def load_ini(ini_path: str) -> dict:
    """
    Read GLBACpypes.ini and return a flat dict of key→value pairs.
    Returns an empty dict when the file is not found (defaults take over).
    """
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding="utf-8")
    result = {}
    for section in cfg.sections():
        for key, val in cfg.items(section):
            result[key] = val
    return result


# ── DB query ──────────────────────────────────────────────────────────────────

MASTER_QUERY = """
SELECT
  gll.id                          AS Location,
  gl.ss_type                      AS device_ss_type,
  gl.name                         AS device_name,
  gl.id                           AS device_id,
  gl.ss_address_value             AS device_table_name,
  CONCAT(gl.ss_address_value,'_metric') AS metric_table_name,
  device.ss_tag                   AS param_type,
  device.ss_address_value         AS param_instance_id,
  device.name                     AS param_id,
  le.param_value                  AS presentValue,
  le.measured_time,
  device.description              AS gl_code,
  ddc.name                        AS ddc_name,
  ddc.id                          AS ddc_ssid
FROM (
  SELECT * FROM gl_subsystem
  WHERE description IS NOT NULL
    AND ss_parent   IS NOT NULL
) device
LEFT JOIN (
  SELECT * FROM gl_subsystem
  WHERE ss_type        IS NOT NULL
    AND ss_address_type != 'GL_SS_ADDRESS_IP'
) gl
  ON device.ss_parent = gl.id
LEFT JOIN gl_subsystem_latest_event le
  ON  le.param_id = device.name
  AND le.ss_id    = gl.id
LEFT JOIN gl_location_subsystem_map glm
  ON glm.ss_id = gl.id
LEFT JOIN gl_location gll
  ON glm.zone_id = gll.id
LEFT JOIN (
  SELECT * FROM gl_subsystem
  WHERE ss_type = 'GL_SS_ADDRESS_BACNET_DDC'
) ddc
  ON gl.ss_parent = ddc.id
"""


def fetch_db_rows(
    db_host: str,
    db_user: str,
    db_password: str,
    db_name: str,
) -> List[dict]:
    """
    Run MASTER_QUERY and return rows as a list of dicts.
    Raises SystemExit on connection failure.
    """
    try:
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
        )
    except mysql.connector.Error as exc:
        msg = (
            "Cannot connect to MySQL at {}@{}/{}\n"
            "  Detail: {}".format(db_user, db_host, db_name, exc)
        )
        raise ConnectionError(msg) from exc

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(MASTER_QUERY)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return rows


# ── live value fetch (reader JSON /data endpoint) ─────────────────────────────

def fetch_live_lookup(
    reader_host: str,
    reader_port: int,
    timeout: int = 10,
) -> Dict[str, Tuple[str, str]]:
    """
    Fetch live point values from the bacnet_reader /data JSON endpoint and
    return a dict:
        gl_code  →  (present_value_str, measured_time_str)

    glWebLibrary.py serves JSON at /data (not an HTML table at /).
    Returns an empty dict when the reader is unreachable so the caller
    can fall back to DB values.
    """
    url = "http://{}:{}/data".format(reader_host, reader_port)
    try:
        with urlopen(url, timeout=timeout) as resp:
            rows = json.loads(resp.read().decode("utf-8", errors="replace"))
    except URLError as exc:
        print(
            "WARNING: Reader web server unreachable at {} — "
            "presentValue will fall back to DB values.\n"
            "  Reason: {}".format(url, exc),
            file=sys.stderr,
        )
        return {}

    lookup: Dict[str, Tuple[str, str]] = {}
    for row in rows:
        gl_code = str(row.get("gl_code") or "").strip()
        if gl_code:
            lookup[gl_code] = (
                str(row.get("present_value") or "").strip(),
                str(row.get("timestamp")     or "").strip(),
            )

    return lookup


# ── snapshot builder ──────────────────────────────────────────────────────────

_NONGL_MONITOR_TYPES = {
    "NONGL_SS_COMMON_HEADER",
    "NONGL_SS_WATER_COOLED_HEADER",
    "NONGL_SS_AIR_COOLED_HEADER",
    "NONGL_SS_DPT_DEVICE",
}


def _default_eqp_metrics(ss_type: str) -> dict:
    """
    Return default Eqp_Metrics for a device.

    Mirrors the JS getMetricData() baseline — no DB reads required.
    For monitor-type headers and CPM devices extra threshold fields are added
    exactly as the JS does when no metric table rows are found.
    """
    base: dict = {
        "rh_cumulative"    : 0,
        "information"      : "data found successfully",
        "Equipment_Faulty" : False,
        "Alarm"            : False,
        "Alarm_code"       : [],
        "downtime"         : 0,
    }
    if ss_type in _NONGL_MONITOR_TYPES:
        base.update({
            "Monitor_Parameter"           : True,
            "THRESHOLD_CROSSING_INTERVAL" : 20,
            "THRESHOLD_CROSSED_TIMESTAMP" : "",
            "THRESHOLD_CROSSED_VALUE"     : 0,
        })
    elif ss_type == "NONGL_SS_CPM":
        base.update({
            "Monitor_Parameter"           : True,
            "THRESHOLD_CROSSING_INTERVAL" : 15,
            "THRESHOLD_CROSSED_TIMESTAMP" : "",
            "THRESHOLD_CROSSED_VALUE"     : 0,
        })
    return base


def _format_date(value) -> Optional[str]:
    """Format a datetime value as 'YYYY-MM-DD HH:MM:SS', or return None."""
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    s = str(value).strip()
    return s if s else None


def build_plant_snapshot(
    db_rows: List[dict],
    live_lookup: Dict[str, Tuple[str, str]],
) -> dict:
    """
    Build the Plant_Snapshot dict from DB structure rows, overlaying live
    present values from the reader wherever available.

    Structure (matches plantsnapshot_mod.json):
      Plant_Snapshot
        └─ <device_ss_type>
             └─ <device_id>
                  ├─ ssType, ddcid, Equipment_Group, BACnetDeviceAddress,
                  │  glSSId, id, name
                  └─ Eqp_Attributes
                       └─ <param_id>
                            ├─ objId, objName
                            ├─ presentValue   ← LIVE (reader) or DB fallback
                            ├─ priority       ← [null × 16]
                            └─ measured_time  ← LIVE timestamp or DB fallback
    """
    snapshot: Dict[str, Dict] = {}
    _priority_template = [None] * 16

    for row in db_rows:
        ss_type      = row.get("device_ss_type")
        device_id    = row.get("device_id")
        param_id     = row.get("param_id")
        gl_code      = row.get("gl_code", "")

        if not ss_type or not device_id:
            continue

        # ── ensure device bucket exists ───────────────────────────────────
        if ss_type not in snapshot:
            snapshot[ss_type] = {}

        if device_id not in snapshot[ss_type]:
            snapshot[ss_type][device_id] = {
                "ssType"             : ss_type,
                "ddcid"              : row.get("ddc_name"),
                "Equipment_Group"    : row.get("Location"),
                "BACnetDeviceAddress": None,
                "glSSId"             : row.get("device_table_name"),
                "id"                 : device_id,
                "name"               : (
                    str(row["device_name"]).strip()
                    if row.get("device_name") else None
                ),
                "Eqp_Attributes"     : {},
                "Eqp_Metrics"        : _default_eqp_metrics(ss_type),
                "EQP_COMPONENTS"     : {},
                "inUse"              : False,
            }

        if not param_id:
            continue

        # ── resolve present value ─────────────────────────────────────────
        # Priority: live reader value > DB latest-event value > None
        if gl_code and gl_code in live_lookup:
            live_pv, live_ts = live_lookup[gl_code]
            present_value = live_pv if live_pv not in ("", "None", "none") else None
            measured_time = live_ts if live_ts else _format_date(row.get("measured_time"))
        else:
            db_pv = row.get("presentValue")
            present_value = str(db_pv) if db_pv is not None else None
            measured_time = _format_date(row.get("measured_time"))

        # ── build objId from numeric BACnet type code + instance ──────────
        param_type     = row.get("param_type", "")
        param_instance = row.get("param_instance_id", "")
        obj_id         = "{}:{}".format(param_type, param_instance) if param_type else None

        snapshot[ss_type][device_id]["Eqp_Attributes"][param_id] = {
            "objId"        : obj_id,
            "objName"      : gl_code,
            "presentValue" : present_value,
            "priority"     : list(_priority_template),
            "measured_time": measured_time,
            "ddc"          : row.get("ddc_name"),
            "ddc_ssid"     : row.get("ddc_ssid"),
        }

    return {"Plant_Snapshot": snapshot}


# ── public API ────────────────────────────────────────────────────────────────

def prepare_plant_snapshot(
    db_host: str        = DEFAULT_DB_HOST,
    db_user: str        = DEFAULT_DB_USER,
    db_password: str    = DEFAULT_DB_PASSWORD,
    db_name: str        = DEFAULT_DB_NAME,
    reader_host: str    = DEFAULT_READER_HOST,
    reader_port: int    = DEFAULT_READER_PORT,
    reader_timeout: int = 10,
) -> dict:
    """
    Importable API — returns the Plant_Snapshot dict.

    Example::
        from plant_snapshot import prepare_plant_snapshot
        snap = prepare_plant_snapshot()
        for ss_type, devices in snap["Plant_Snapshot"].items():
            for dev_id, device in devices.items():
                for p_name, attr in device["Eqp_Attributes"].items():
                    print(ss_type, p_name, attr["presentValue"])
    """
    db_rows     = fetch_db_rows(db_host, db_user, db_password, db_name)
    live_lookup = fetch_live_lookup(reader_host, reader_port, reader_timeout)
    return build_plant_snapshot(db_rows, live_lookup)


# ── output helper ─────────────────────────────────────────────────────────────

def write_output(snapshot: dict, out_path: Optional[str], indent: int) -> None:
    text = json.dumps(snapshot, indent=indent, default=str)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        devices = sum(len(v) for v in snapshot.get("Plant_Snapshot", {}).values())
        points  = sum(
            len(d.get("Eqp_Attributes", {}))
            for devs in snapshot.get("Plant_Snapshot", {}).values()
            for d in devs.values()
        )
        print("Plant snapshot written to '{}'.".format(out_path))
        print("  SS types : {}".format(len(snapshot.get("Plant_Snapshot", {}))))
        print("  Devices  : {}".format(devices))
        print("  Points   : {}".format(points))
    else:
        print(text)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Build a Plant_Snapshot JSON with live BACnet values. "
            "Structure comes from the DB; present values come from the "
            "bacnet_reader.py web server."
        )
    )
    p.add_argument("--ini",          default=DEFAULT_INI,
                   help="GLBACpypes.ini path (default: {})".format(DEFAULT_INI))
    p.add_argument("--db-host",      default=None,
                   help="MySQL host (overrides INI)")
    p.add_argument("--db-user",      default=None,
                   help="MySQL user (overrides INI)")
    p.add_argument("--db-password",  default=None,
                   help="MySQL password (overrides INI)")
    p.add_argument("--db-name",      default=None,
                   help="MySQL database name (overrides INI)")
    p.add_argument("--reader-host",  default=None,
                   help="bacnet_reader.py host (default: {})".format(DEFAULT_READER_HOST))
    p.add_argument("--reader-port",  type=int, default=None,
                   help="PBS2Webport from GLBACpypes.ini (default: {})".format(DEFAULT_READER_PORT))
    p.add_argument("--out",          default=DEFAULT_OUT,
                   help="Output JSON file ('-' for stdout, default: {})".format(DEFAULT_OUT))
    p.add_argument("--indent",       type=int, default=2,
                   help="JSON indent width (default: 2)")
    p.add_argument("--timeout",      type=int, default=10,
                   help="HTTP timeout in seconds for reader (default: 10)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # ── load INI for defaults ─────────────────────────────────────────────
    ini = load_ini(args.ini)

    db_host     = args.db_host     or ini.get("databasehost",     DEFAULT_DB_HOST)
    db_user     = args.db_user     or ini.get("databaseuser",     DEFAULT_DB_USER)
    db_password = args.db_password or ini.get("databasepassword", DEFAULT_DB_PASSWORD)
    db_name     = args.db_name     or ini.get("ibms_database_name", DEFAULT_DB_NAME)
    reader_host = args.reader_host or DEFAULT_READER_HOST
    reader_port = args.reader_port or int(ini.get("pbs2webport", DEFAULT_READER_PORT))

    out_path = None if args.out == "-" else args.out

    print("Querying DB  : {}@{}/{}".format(db_user, db_host, db_name))
    try:
        db_rows = fetch_db_rows(db_host, db_user, db_password, db_name)
    except ConnectionError as exc:
        sys.exit("ERROR: {}".format(exc))
    print("  DB rows    : {}".format(len(db_rows)))

    print("Fetching live: http://{}:{}/".format(reader_host, reader_port))
    live_lookup = fetch_live_lookup(reader_host, reader_port, args.timeout)
    print("  Live points: {}".format(len(live_lookup)))

    snapshot = build_plant_snapshot(db_rows, live_lookup)
    write_output(snapshot, out_path, args.indent)
