"""
DQ Tier 1 — inline checks applied to every PointReading before Kafka publish.
Implements the 8 checks from 06_DATA_QUALITY_LAYER.md.
State (previous values, frozen counters) lives in-process per point.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .models import PointReading, QualityEnvelope

log = logging.getLogger("dq_tier1")

# ---- Per-point state --------------------------------------------------------

@dataclass
class PointState:
    prev_value: Optional[float] = None
    prev_ts: Optional[float] = None        # unix timestamp of last read
    frozen_count: int = 0                  # consecutive identical readings
    last_seen_ts: Optional[float] = None   # wall clock of last GOOD reading


_state: dict[str, PointState] = {}


def _get_state(point_id: str) -> PointState:
    if point_id not in _state:
        _state[point_id] = PointState()
    return _state[point_id]


# ---- DQ config defaults (overridden by app.data_quality_config in Postgres) -

_RANGE_DEFAULTS: dict[str, tuple[float, float]] = {
    "analogInput":  (-50.0, 250.0),
    "analogOutput": (0.0,   100.0),
    "analogValue":  (-50.0, 250.0),
}
_SPIKE_MAX_DELTA_PCT = 50.0     # >50% change from prev is a spike
_STALE_MAX_AGE_S     = 300.0   # >5 min without update = stale
_FROZEN_MIN_UNIQUE   = 2        # need ≥2 unique values in last 10 readings


# ---- Check functions --------------------------------------------------------

def _check_null(reading: PointReading) -> None:
    if reading.value_num is None and reading.value_str is None:
        reading.quality.degrade("NULL_VALUE", "BAD")


def _check_type(reading: PointReading) -> None:
    analog_types = {"analogInput", "analogOutput", "analogValue"}
    if reading.object_type in analog_types and reading.value_num is None:
        if reading.value_str is not None:
            reading.quality.degrade("TYPE_MISMATCH", "UNCERTAIN")


def _check_range(reading: PointReading) -> None:
    if reading.value_num is None:
        return
    lo, hi = _RANGE_DEFAULTS.get(reading.object_type, (-1e9, 1e9))
    if reading.value_num < lo:
        reading.quality.degrade("RANGE_LOW", "BAD")
    elif reading.value_num > hi:
        reading.quality.degrade("RANGE_HIGH", "BAD")


def _check_spike(reading: PointReading, state: PointState) -> None:
    if reading.value_num is None or state.prev_value is None:
        return
    if state.prev_value == 0:
        return
    delta_pct = abs(reading.value_num - state.prev_value) / abs(state.prev_value) * 100
    if delta_pct > _SPIKE_MAX_DELTA_PCT:
        reading.quality.degrade("SPIKE", "UNCERTAIN")


def _check_stale(reading: PointReading, state: PointState) -> None:
    now = time.time()
    if state.last_seen_ts is not None:
        age = now - state.last_seen_ts
        if age > _STALE_MAX_AGE_S:
            reading.quality.degrade("STALE", "UNCERTAIN")


def _check_frozen(reading: PointReading, state: PointState) -> None:
    if reading.value_num is None:
        return
    if state.prev_value is not None and reading.value_num == state.prev_value:
        state.frozen_count += 1
    else:
        state.frozen_count = 0
    # 10 consecutive identical → frozen
    if state.frozen_count >= 10:
        reading.quality.degrade("FROZEN", "UNCERTAIN")


def _check_unit(reading: PointReading) -> None:
    # Basic sanity: temperature readings must be plausible
    if "temp" in reading.point_id.lower() and reading.value_num is not None:
        if not (-30.0 <= reading.value_num <= 120.0):
            reading.quality.degrade("UNIT_IMPLAUSIBLE", "BAD")


def _check_format(reading: PointReading) -> None:
    if not reading.point_id:
        reading.quality.degrade("MISSING_POINT_ID", "BAD")
    if reading.measured_at is None:
        reading.quality.degrade("MISSING_TIMESTAMP", "BAD")


# ---- Public entry point -----------------------------------------------------

def apply_tier1(reading: PointReading) -> PointReading:
    """
    Apply all 8 Tier 1 checks in-place.
    Updates per-point state after checks.
    Returns the same reading (with quality populated).
    """
    state = _get_state(reading.point_id)

    _check_null(reading)
    _check_type(reading)
    _check_range(reading)
    _check_spike(reading, state)
    _check_stale(reading, state)
    _check_frozen(reading, state)
    _check_unit(reading)
    _check_format(reading)

    # Update state
    if reading.value_num is not None:
        state.prev_value = reading.value_num
    state.last_seen_ts = time.time()

    return reading
