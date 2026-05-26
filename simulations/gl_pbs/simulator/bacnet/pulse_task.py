"""
pulse_task — PulseTask: recurring BACnet value update task.

SRP: Updates equipment presentValues, applies operation rules and
     parameter relationships at a fixed interval.
     No HTTP, no config loading, no BACnet protocol.

DIP: Receives EquipmentRegistry at construction instead of using globals.

Port of PulseTask in bacnet_simulator.py.

Relationship logic
------------------
GLSDeploymentDetails.json may contain an ``EQP_PARAM_RELATIONSHIPS`` block:

    "EQP_PARAM_RELATIONSHIPS": {
        "CHILLER": {"master": "sts_on_off_00"},
        "AHU":     {"master": "SAF_VFD_On_Off_Fbk"},
        ...
    }

``master`` names the binary parameter that indicates whether the equipment
is running.  When the master is ``active`` (ON), all analog params in the
same equipment instance receive a small random walk within [lowLimit, highLimit].
When the master is ``inactive`` (OFF), analogs drift gradually toward their
idle value (0 if that is within range, otherwise lowLimit).

If no master is configured for an equipment type, a heuristic is used:
the first binary param whose presentValue is ``'active'`` or ``'inactive'``
is treated as the switch.  If none is found, ON is assumed.

Values are **always clamped** to [lowLimit, highLimit] after every update,
preventing runaway values regardless of how presentValue was set.
"""
from __future__ import annotations

import logging
import random
from typing import Optional, Tuple

from bacpypes.basetypes import DateTime
from bacpypes.debugging import ModuleLogger, bacpypes_debugging
from bacpypes.primitivedata import Date, Time
from bacpypes.task import RecurringTask

from simulator.equipment.registry import EquipmentRegistry
from simulator.objects.writable_objects import (
    WritableAnalogInputObject,
    WritableAnalogOutputObject,
    WritableAnalogValueObject,
    WritableBinaryInputObject,
    WritableBinaryOutputObject,
    WritableBinaryValueObject,
)

logger = logging.getLogger(__name__)
_debug = 0
_log = ModuleLogger(globals())

_ANALOG_TYPES = (
    WritableAnalogValueObject,
    WritableAnalogInputObject,
    WritableAnalogOutputObject,
)
_BINARY_TYPES = (
    WritableBinaryValueObject,
    WritableBinaryInputObject,
    WritableBinaryOutputObject,
)

# Random drift as a fraction of the full [low, high] range per tick
_ACTIVE_DRIFT_FRACTION = 0.02
# Fraction of the gap to idle that is closed each tick when OFF
_IDLE_PULL_FRACTION = 0.30


@bacpypes_debugging
class PulseTask(RecurringTask):
    """
    Recurring task that:

    1. Applies ``EQP_OPS_RULES`` from the registry's operation_specs
       (copies presentValue from one parameter to another).
    2. Determines on/off state via ``EQP_PARAM_RELATIONSHIPS`` (or heuristic).
    3. When ON  → applies a small clamped random walk on each analog param.
       When OFF → drifts each analog param toward its idle value (0 or lowLimit).
    4. Always clamps every analog presentValue to [lowLimit, highLimit].
    """

    def __init__(
        self,
        registry: EquipmentRegistry,
        increment: int = 1,
        interval_ms: float = 10_000,
    ) -> None:
        if _debug:
            PulseTask._debug('__init__ increment=%r interval_ms=%r', increment, interval_ms)
        RecurringTask.__init__(self, interval_ms)
        self.install_task()

        self._registry = registry
        self.increment = increment
        self.value_change_time = DateTime(
            date=Date().now().value, time=Time().now().value,
        )

    # ── RecurringTask API ──────────────────────────────────────────────────────

    def process_task(self) -> None:
        if _debug:
            PulseTask._debug('process_task')

        specs = self._registry.operation_specs
        ops_rules: dict = specs.get('EQP_OPS_RULES', {})
        rel_rules: dict = specs.get('EQP_PARAM_RELATIONSHIPS', {})
        disable_random: bool = bool(specs.get('Disable_Random_PresentValue_Updates', False))

        for eqp_type, eqp_instances in self._registry.get_all().items():
            rules = ops_rules.get(eqp_type) or None
            master_name: Optional[str] = rel_rules.get(eqp_type, {}).get('master')

            for eqp_id, params in eqp_instances.items():
                # Step 1 — mirror command → status via ops rules
                if rules:
                    self._apply_operation_rules(params, rules)

                # Step 2 — determine running state for this instance
                is_on = self._get_on_off_state(params, master_name)

                # Step 3 — update / drift each parameter
                for param_name, obj in params.items():
                    if param_name == 'OtherDetails':
                        continue
                    if not disable_random:
                        # Skip setpoint params
                        if hasattr(obj, 'description') and str(obj.description).endswith('_SP'):
                            pass
                        elif is_on:
                            self._drift_active(obj)
                        elif param_name != master_name:
                            self._drift_idle(obj)

                    # Step 4 — always clamp to defined limits
                    self._clamp(obj)

        self.value_change_time = DateTime(
            date=Date().now().value, time=Time().now().value,
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    def _apply_operation_rules(self, params: dict, rules: dict) -> None:
        """
        Port of applyOperationRules().
        Copies presentValue from source param to target param within the same equipment.
        """
        from bacpypes.basetypes import TimeStamp
        now = DateTime(date=Date().now().value, time=Time().now().value)
        for target, source in rules.items():
            if target in params and source in params:
                params[target].presentValue = params[source].presentValue
                params[target].lastCommandTime = TimeStamp(dateTime=now)

    def _get_on_off_state(self, params: dict, master_name: Optional[str]) -> bool:
        """
        Returns True if equipment is ON, False if OFF.

        Priority:
          1. Named master param from EQP_PARAM_RELATIONSHIPS.
          2. Heuristic: first binary param whose presentValue is 'active'/'inactive'.
          3. Default → True (assume always on if no binary indicator found).
        """
        if master_name and master_name in params:
            return getattr(params[master_name], 'presentValue', None) == 'active'

        # Heuristic fallback
        for name, obj in params.items():
            if name == 'OtherDetails':
                continue
            if isinstance(obj, _BINARY_TYPES):
                pv = getattr(obj, 'presentValue', None)
                if pv in ('active', 'inactive'):
                    return pv == 'active'
        return True

    def _drift_active(self, obj) -> None:
        """
        Apply a small random walk on analog params while the equipment is ON.
        The drift is ±2% of the full [lowLimit, highLimit] range, then clamped.
        Binary and multi-state objects are left unchanged.
        """
        if not isinstance(obj, _ANALOG_TYPES):
            return
        low, high = self._get_limits(obj)
        if low >= high:
            return
        drift = (high - low) * _ACTIVE_DRIFT_FRACTION * random.uniform(-1.0, 1.0)
        new_val = float(obj.presentValue) + drift
        obj.presentValue = round(max(low, min(high, new_val)), 2)

    def _drift_idle(self, obj) -> None:
        """
        Gradually move analog params toward their idle value while the equipment
        is OFF.  Idle = 0.0 when that falls within [lowLimit, highLimit], otherwise
        = lowLimit (e.g. a temperature that doesn't go to zero when a chiller stops).
        Binary and multi-state objects are left unchanged.
        """
        if not isinstance(obj, _ANALOG_TYPES):
            return
        low, high = self._get_limits(obj)
        idle = 0.0 if low <= 0.0 <= high else low
        current = float(obj.presentValue)
        if abs(current - idle) < 0.01:
            return
        obj.presentValue = round(current + (idle - current) * _IDLE_PULL_FRACTION, 2)

    def _clamp(self, obj) -> None:
        """
        Clamp analog presentValue to [lowLimit, highLimit].
        No-op for binary and multi-state objects.
        """
        if not isinstance(obj, _ANALOG_TYPES):
            return
        low, high = self._get_limits(obj)
        if low >= high:
            return
        pv = float(obj.presentValue)
        clamped = max(low, min(high, pv))
        if clamped != pv:
            obj.presentValue = round(clamped, 2)

    @staticmethod
    def _get_limits(obj) -> Tuple[float, float]:
        """Return (lowLimit, highLimit) as floats, with safe fallbacks."""
        low = obj.lowLimit if obj.lowLimit is not None else 0.0
        high = obj.highLimit if obj.highLimit is not None else 100.0
        return float(low), float(high)
