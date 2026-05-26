#!/usr/bin/env python
"""
plant_snapshot_api.py

WebSocket server that streams live Plant_Snapshot JSON to all connected clients.

Architecture
------------
  1. DB rows (device/point structure) are loaded ONCE at startup and held in
     memory.  The heavy multi-JOIN query never re-runs unless explicitly
     requested via {"action": "reload_db"}.

  2. A single background task polls bacnet_reader every --interval seconds,
     builds the snapshot with live present values, and broadcasts it to every
     connected client in one shot.

  3. Each new client immediately receives the latest snapshot on connect —
     no waiting for the next interval.

WebSocket endpoint
------------------
  ws://localhost:9000/

  Outbound (server -> client):
    Full Plant_Snapshot JSON on connect, then again every --interval seconds.

  Inbound (client -> server):
    {"action": "reload_db"}   -- re-fetch DB rows into memory, responds with
                                  {"action":"reload_db","status":"ok","db_rows":N}

Usage
-----
    python plant_snapshot_api.py
    python plant_snapshot_api.py --port 9000 --interval 5

Dependencies
------------
    pip install websockets
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor

try:
    import websockets
except ImportError:
    sys.exit("ERROR: 'websockets' package required -- pip install websockets")

try:
    from plant_snapshot import (
        fetch_db_rows,
        fetch_live_lookup,
        build_plant_snapshot,
        load_ini,
        DEFAULT_INI,
        DEFAULT_DB_HOST,
        DEFAULT_DB_USER,
        DEFAULT_DB_PASSWORD,
        DEFAULT_DB_NAME,
        DEFAULT_READER_HOST,
        DEFAULT_READER_PORT,
    )
except ImportError as exc:
    sys.exit(
        "ERROR: Cannot import plant_snapshot.py -- make sure it is in the same "
        "directory.\n  Detail: {}".format(exc)
    )

# ── defaults ──────────────────────────────────────────────────────────────────

API_DEFAULT_PORT = 9000
DEFAULT_INTERVAL = 5        # seconds between snapshot pushes

# ── module-level state ────────────────────────────────────────────────────────

_config: dict = {
    "db_host"    : DEFAULT_DB_HOST,
    "db_user"    : DEFAULT_DB_USER,
    "db_password": DEFAULT_DB_PASSWORD,
    "db_name"    : DEFAULT_DB_NAME,
    "reader_host": DEFAULT_READER_HOST,
    "reader_port": DEFAULT_READER_PORT,
    "db_rows"    : [],
    "interval"   : DEFAULT_INTERVAL,
}

# All currently connected WebSocket clients
_clients: set = set()

# Thread-pool for blocking I/O (DB query, HTTP fetch to reader)
_executor = ThreadPoolExecutor(max_workers=2)


# ── blocking helpers (always run via loop.run_in_executor) ────────────────────

def _load_db_rows() -> None:
    """Fetch device/point structure from DB.  Blocking -- use executor."""
    rows = fetch_db_rows(
        _config["db_host"], _config["db_user"],
        _config["db_password"], _config["db_name"],
    )
    _config["db_rows"] = rows
    print("  [DB] Loaded {} rows.".format(len(rows)))


def _build_snapshot() -> dict:
    """
    Fetch live present values from bacnet_reader and build the full snapshot.
    Uses cached db_rows -- no DB hit.  Blocking -- use executor.
    """
    live_lookup = fetch_live_lookup(_config["reader_host"], _config["reader_port"])
    return build_plant_snapshot(_config["db_rows"], live_lookup)


# ── background broadcast loop ─────────────────────────────────────────────────

async def _broadcast_loop() -> None:
    """
    Runs forever in the background.  Every `interval` seconds:
      1. Calls bacnet_reader ONCE to get live present values.
      2. Builds the Plant_Snapshot from in-memory DB rows.
      3. Pushes the JSON to every connected client.

    bacnet_reader is hit exactly once per interval regardless of client count.
    """
    loop = asyncio.get_running_loop()

    while True:
        await asyncio.sleep(_config["interval"])

        if not _clients:
            continue

        try:
            snapshot = await loop.run_in_executor(_executor, _build_snapshot)
        except Exception as exc:
            print("  [BROADCAST] Snapshot build error: {}".format(exc))
            continue

        message = json.dumps(snapshot, default=str)

        dead: set = set()
        for ws in list(_clients):
            try:
                await ws.send(message)
            except Exception:
                dead.add(ws)
        _clients.difference_update(dead)

        print("  [BROADCAST] Pushed to {} client(s).".format(len(_clients)))


# ── per-client WebSocket handler ──────────────────────────────────────────────

async def _handle_client(websocket, *_) -> None:
    """
    Lifecycle for one WebSocket connection:
      - On connect: add to _clients, send current snapshot immediately.
      - While connected: listen for inbound commands.
      - On disconnect: remove from _clients.
    """
    _clients.add(websocket)
    addr = getattr(websocket, "remote_address", "unknown")
    print("  [WS] Connected: {}  (clients: {})".format(addr, len(_clients)))

    loop = asyncio.get_running_loop()

    try:
        # Send current snapshot immediately so client has data without waiting
        try:
            snapshot = await loop.run_in_executor(_executor, _build_snapshot)
            await websocket.send(json.dumps(snapshot, default=str))
        except Exception as exc:
            await websocket.send(json.dumps(
                {"error": "initial snapshot failed", "detail": str(exc)}
            ))

        # Listen for inbound commands from this client
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue

            if msg.get("action") == "reload_db":
                print("  [WS] reload_db requested by {}".format(addr))
                try:
                    await loop.run_in_executor(_executor, _load_db_rows)
                    await websocket.send(json.dumps({
                        "action" : "reload_db",
                        "status" : "ok",
                        "db_rows": len(_config["db_rows"]),
                    }))
                except Exception as exc:
                    await websocket.send(json.dumps({
                        "action": "reload_db",
                        "status": "error",
                        "detail": str(exc),
                    }))

    except Exception:
        pass
    finally:
        _clients.discard(websocket)
        print("  [WS] Disconnected: {}  (clients: {})".format(addr, len(_clients)))


# ── server entry point ────────────────────────────────────────────────────────

async def _run(api_port: int) -> None:
    loop = asyncio.get_running_loop()

    print("Loading device/point structure from DB...")
    try:
        await loop.run_in_executor(_executor, _load_db_rows)
    except ConnectionError as exc:
        sys.exit("ERROR: Cannot connect to DB at startup -- {}".format(exc))

    asyncio.create_task(_broadcast_loop())

    async with websockets.serve(_handle_client, "0.0.0.0", api_port):
        print("Plant Snapshot WebSocket server started.")
        print("  WebSocket     : ws://localhost:{}/".format(api_port))
        print("  DB            : {}@{}/{}".format(
            _config["db_user"], _config["db_host"], _config["db_name"]))
        print("  Reader source : http://{}:{}/".format(
            _config["reader_host"], _config["reader_port"]))
        print("  Push interval : {} s".format(_config["interval"]))
        print("  Press Ctrl+C to stop.\n")
        await asyncio.Future()   # run until interrupted


def run_api_server(
    api_port: int    = API_DEFAULT_PORT,
    db_host: str     = DEFAULT_DB_HOST,
    db_user: str     = DEFAULT_DB_USER,
    db_password: str = DEFAULT_DB_PASSWORD,
    db_name: str     = DEFAULT_DB_NAME,
    reader_host: str = DEFAULT_READER_HOST,
    reader_port: int = DEFAULT_READER_PORT,
    interval: float  = DEFAULT_INTERVAL,
) -> None:
    """Start the WebSocket server (blocking)."""
    _config["db_host"]     = db_host
    _config["db_user"]     = db_user
    _config["db_password"] = db_password
    _config["db_name"]     = db_name
    _config["reader_host"] = reader_host
    _config["reader_port"] = reader_port
    _config["interval"]    = interval

    try:
        asyncio.run(_run(api_port))
    except KeyboardInterrupt:
        print("\nWebSocket server stopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Stream live BACnet Plant_Snapshot data over WebSocket. "
            "DB structure loaded once at startup; live values pushed from "
            "bacnet_reader.py every --interval seconds."
        )
    )
    p.add_argument("--port",        type=int,   default=API_DEFAULT_PORT,
                   help="WebSocket port (default: {}).".format(API_DEFAULT_PORT))
    p.add_argument("--interval",    type=float, default=DEFAULT_INTERVAL,
                   help="Push interval in seconds (default: {}).".format(DEFAULT_INTERVAL))
    p.add_argument("--db-host",     default=None,
                   help="MySQL host (default from GLBACpypes.ini).")
    p.add_argument("--db-user",     default=None,
                   help="MySQL user (default from GLBACpypes.ini).")
    p.add_argument("--db-password", default=None,
                   help="MySQL password (default from GLBACpypes.ini).")
    p.add_argument("--db-name",     default=None,
                   help="MySQL database name (default from GLBACpypes.ini).")
    p.add_argument("--reader-host", default=DEFAULT_READER_HOST,
                   help="bacnet_reader.py host (default: {}).".format(DEFAULT_READER_HOST))
    p.add_argument("--reader-port", type=int, default=None,
                   help="PBS2Webport (default from GLBACpypes.ini).")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    ini = load_ini(DEFAULT_INI)

    db_host     = args.db_host     or ini.get("databasehost",       DEFAULT_DB_HOST)
    db_user     = args.db_user     or ini.get("databaseuser",       DEFAULT_DB_USER)
    db_password = args.db_password or ini.get("databasepassword",   DEFAULT_DB_PASSWORD)
    db_name     = args.db_name     or ini.get("ibms_database_name", DEFAULT_DB_NAME)
    reader_port = args.reader_port or int(ini.get("pbs2webport",    DEFAULT_READER_PORT))

    run_api_server(
        api_port    = args.port,
        db_host     = db_host,
        db_user     = db_user,
        db_password = db_password,
        db_name     = db_name,
        reader_host = args.reader_host,
        reader_port = reader_port,
        interval    = args.interval,
    )
