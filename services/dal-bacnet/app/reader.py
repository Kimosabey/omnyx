"""
BACnet reader — polls all DDCs via ReadPropertyMultiple (RPM).
Falls back to single ReadProperty per point on RPM rejection.
Uses bacpypes 0.18.6 (same version as gl_pbs simulator).
"""
import logging
import threading
import time
from configparser import ConfigParser
from datetime import datetime, timezone
from typing import Optional
import json

from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.core import run as bacpypes_run, stop as bacpypes_stop, deferred
from bacpypes.pdu import Address
from bacpypes.apdu import (
    ReadPropertyMultipleRequest,
    ReadAccessSpecification,
    PropertyReference,
    ReadPropertyRequest,
)
from bacpypes.primitivedata import ObjectIdentifier
from bacpypes.iocb import IOCB

from .config import settings
from .csv_loader import load_point_map, PointMeta
from .models import PointReading, QualityEnvelope
from .dq_tier1 import apply_tier1
from . import metrics

log = logging.getLogger("bacnet_reader")

# ---- BACnet application (one per service instance) -------------------------

_app: Optional[BIPSimpleApplication] = None
_app_lock = threading.Lock()


def _init_bacnet_app() -> BIPSimpleApplication:
    """Create a BIPSimpleApplication using device ID 9999 (reader identity)."""
    device = LocalDeviceObject(
        objectName="OMNYX-DAL",
        objectIdentifier=9999,
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15,
    )
    app = BIPSimpleApplication(device, "0.0.0.0")
    log.info("BACnet application initialised (device 9999)")
    return app


# ---- Controller map ---------------------------------------------------------

def load_controller_map(ini_path: str) -> dict[str, str]:
    """
    Parse GLBACpypes.ini and return {ddc_id: "ip:port"}.
    The ini has a key controllermap = {"DDC01": "127.0.0.1:2001", ...}
    """
    cp = ConfigParser()
    cp.read(ini_path)
    raw = cp.get("BACpypes", "controllermap", fallback="{}")
    try:
        data = json.loads(raw)
        log.info("Controller map: %s", data)
        return data
    except Exception as exc:
        log.error("Failed to parse controllermap from %s: %s", ini_path, exc)
        return {}


# ---- RPM read ---------------------------------------------------------------

def _rpm_read(app: BIPSimpleApplication,
              address: str,
              point_list: list[PointMeta]) -> dict[tuple, Optional[float]]:
    """
    Send a ReadPropertyMultiple request for all points in point_list.
    Returns {(obj_type, obj_id): value_or_None}.
    """
    results: dict[tuple, Optional[float]] = {}

    # Build ReadAccessSpecification list
    specs = []
    for meta in point_list:
        oid = ObjectIdentifier(f"{meta.obj_type}:{meta.obj_id}")
        prop_ref = PropertyReference(propertyIdentifier="presentValue")
        spec = ReadAccessSpecification(
            objectIdentifier=oid,
            listOfPropertyReferences=[prop_ref],
        )
        specs.append(spec)

    request = ReadPropertyMultipleRequest(
        listOfReadAccessSpecs=specs,
        destination=Address(address),
    )

    iocb = IOCB(request)
    iocb.set_timeout(settings.bacnet_timeout_s)
    deferred(app.request_io, iocb)
    iocb.wait()

    if iocb.ioError:
        raise RuntimeError(f"RPM error from {address}: {iocb.ioError}")

    # Parse response
    for result in iocb.ioResponse.listOfReadAccessResults:
        obj_id_str  = str(result.objectIdentifier)
        obj_type    = obj_id_str.split(":")[0] if ":" in obj_id_str else obj_id_str
        obj_instance = int(obj_id_str.split(":")[1]) if ":" in obj_id_str else 0

        for prop_result in result.listOfResults:
            if hasattr(prop_result, "readResult") and prop_result.readResult:
                raw = prop_result.readResult.propertyValue
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    # booleans, enum values
                    val = 1.0 if raw else 0.0
                results[(obj_type, obj_instance)] = val
            else:
                results[(obj_type, obj_instance)] = None

    return results


def _single_reads(app: BIPSimpleApplication,
                  address: str,
                  point_list: list[PointMeta]) -> dict[tuple, Optional[float]]:
    """Fallback: read one point at a time."""
    results: dict[tuple, Optional[float]] = {}
    for meta in point_list:
        request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(f"{meta.obj_type}:{meta.obj_id}"),
            propertyIdentifier="presentValue",
            destination=Address(address),
        )
        iocb = IOCB(request)
        iocb.set_timeout(settings.bacnet_timeout_s)
        deferred(app.request_io, iocb)
        iocb.wait()
        if iocb.ioError:
            results[(meta.obj_type, meta.obj_id)] = None
        else:
            try:
                results[(meta.obj_type, meta.obj_id)] = float(iocb.ioResponse.propertyValue)
            except Exception:
                results[(meta.obj_type, meta.obj_id)] = None
    return results


# ---- Poll cycle -------------------------------------------------------------

def poll_device(app: BIPSimpleApplication,
                ddc_id: str,
                address: str,
                point_map: dict[tuple, PointMeta],
                tenant_id: str,
                prev_values: dict[str, Optional[float]],
                cov_threshold: float) -> list[PointReading]:
    """
    Read all points for one DDC.
    Returns list of PointReadings that pass CoV filter (or all if heartbeat).
    """
    point_list = list(point_map.values())
    now = datetime.now(timezone.utc)
    readings: list[PointReading] = []

    # Try RPM first; fall back to single reads on any error
    try:
        values = _rpm_read(app, address, point_list)
    except Exception as exc:
        log.warning("RPM failed for %s (%s), falling back to single reads", ddc_id, exc)
        try:
            values = _single_reads(app, address, point_list)
        except Exception as exc2:
            log.error("Single reads also failed for %s: %s", ddc_id, exc2)
            return []

    for meta in point_list:
        key = (meta.obj_type, meta.obj_id)
        raw_val = values.get(key)

        # CoV filter
        prev = prev_values.get(meta.gl_code)
        if prev is not None and raw_val is not None:
            try:
                if abs(raw_val - prev) / (abs(prev) + 1e-9) * 100 < cov_threshold:
                    continue  # no meaningful change
            except ZeroDivisionError:
                pass

        reading = PointReading(
            point_id=meta.gl_code,
            device_id=ddc_id,
            tenant_id=tenant_id,
            measured_at=now,
            value_num=raw_val,
            object_type=meta.obj_type,
            object_instance=meta.obj_id,
        )

        apply_tier1(reading)
        readings.append(reading)

        if raw_val is not None:
            prev_values[meta.gl_code] = raw_val

    return readings


# ---- Background BACnet thread -----------------------------------------------

def start_bacnet_thread() -> BIPSimpleApplication:
    """Start bacpypes core event loop in a daemon thread, return the app."""
    global _app
    with _app_lock:
        if _app is None:
            _app = _init_bacnet_app()
            t = threading.Thread(target=bacpypes_run, daemon=True, name="bacpypes")
            t.start()
            time.sleep(1.0)  # give the event loop time to start
    return _app


def stop_bacnet() -> None:
    bacpypes_stop()
