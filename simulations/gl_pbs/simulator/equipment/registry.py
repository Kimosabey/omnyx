"""
registry — EquipmentRegistry, the single authoritative store for
           all simulated BACnet equipment objects.

SRP: Holds equipment state; does not load config or simulate updates.
DIP: Loader and PulseTask receive this instance via constructor injection.

Replaces the module-level globals:
    glEqpObjects, glEqpParamIDs_Now, glEqpTLIDs_Now,
    glEqpOperationSpecs, siteDDCId
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

# Type alias: {eqp_type: {eqp_id: {param_name: BACnetObj | OtherDetails}}}
EqpStore = Dict[str, Dict[str, Dict[str, Any]]]


class EquipmentRegistry:
    """
    Thread-safe-ish store for all simulated equipment objects.

    Structure:
        registry[eqp_type][eqp_id][param_name] = BACnet object
        registry[eqp_type][eqp_id]['OtherDetails'] = {'EQUIPMENT_ID': ..., ...}
    """

    def __init__(self) -> None:
        self._store: EqpStore = {}

        # Mutable counters used during object-ID allocation (replaced globals)
        self.param_ids_now: Dict[str, int] = {}
        self.trend_log_ids_now: Dict[str, int] = {}

        # Operational rules/specs loaded from GLSDeploymentDetails.json
        self.operation_specs: dict = {}

        # DDC address read from the first row of the site CSV
        self.site_ddc_id: Optional[str] = None

    # ── equipment-type management ──────────────────────────────────────────────

    def ensure_type(self, eqp_type: str) -> None:
        if eqp_type not in self._store:
            self._store[eqp_type] = {}

    def add_equipment(self, eqp_type: str, eqp_id: str, equipment: dict) -> None:
        self.ensure_type(eqp_type)
        self._store[eqp_type][eqp_id] = equipment

    def get_equipment(self, eqp_type: str, eqp_id: str) -> Optional[dict]:
        return self._store.get(eqp_type, {}).get(eqp_id)

    def get_all(self) -> EqpStore:
        return self._store

    def get_type(self, eqp_type: str) -> Dict[str, dict]:
        return self._store.get(eqp_type, {})

    def has_type(self, eqp_type: str) -> bool:
        return eqp_type in self._store

    def types(self) -> Iterator[str]:
        return iter(self._store)

    def count_of_type(self, eqp_type: str) -> int:
        return len(self._store.get(eqp_type, {}))

    def all_bacnet_objects(self):
        """Iterate every registered BACnet parameter/trend-log object."""
        for eqp_instances in self._store.values():
            for params in eqp_instances.values():
                for param_name, obj in params.items():
                    if param_name != 'OtherDetails':
                        yield obj
