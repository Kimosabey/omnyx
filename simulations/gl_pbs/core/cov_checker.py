"""
CoVChecker — Change-of-Value detector for BACnet point data.

SRP: Only responsible for maintaining per-device CoV state and computing
     whether a measured value represents a Change-of-Value.

Extracted from ReadPointListThread.inThreadComputePointListCoV() in the
original bacnet_reader.py.  The previous_values dict is passed by
reference from PointListStore so state persists across read cycles.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from glDASLibrary import (
    myprint,
    printTrace,
    processEquipmentCode,
    getstrTimeNow,
)


class CoVChecker:
    """
    Stateful, per-device Change-of-Value detector.

    State record layout (previous_values[device_addr][bacnet_obj_id]):
        [objectName, lastTimestamp, lastPresentValue, p_name, e_id, eqp_tableName]

    The dict is a live reference to PointListStore's storage so mutations
    here are automatically persisted across read cycles without any
    explicit write-back.
    """

    def __init__(
        self,
        previous_values: dict,
        heartbeat_minutes: float,
        threshold_percent: float,
        table_name_length: int = 12,
    ) -> None:
        self.previous_values = previous_values
        self.heartbeat_minutes = heartbeat_minutes
        self.threshold_fraction = threshold_percent * 0.01
        self.table_name_length = table_name_length

    # ── public API ───────────────────────────────────────────────────────

    def update(
        self,
        device_address: str,
        bacnet_obj_id: str,
        property_id: str,           # 'objectName' | 'presentValue'
        property_value: Any,
        measured_time: Optional[str] = None,
        param_type: str = 'analog', # 'analog' | 'binary' | 'multiState'
    ) -> bool:
        """
        Update internal state for (device_address, bacnet_obj_id).
        Returns True when a Change-of-Value is detected for presentValue
        properties; always False for objectName properties.

        Direct port of inThreadComputePointListCoV() — logic is unchanged,
        GL_GLOBALS references replaced by constructor params.
        """
        if measured_time is None:
            measured_time = getstrTimeNow()

        if property_id == 'objectName':
            return self._handle_object_name(
                device_address, bacnet_obj_id, property_value, measured_time
            )
        else:
            return self._handle_present_value(
                device_address, bacnet_obj_id, property_value,
                measured_time, param_type
            )

    def get_record(
        self, device_address: str, bacnet_obj_id: str
    ) -> Optional[list]:
        """Return the full state record or None if not yet seen."""
        return self.previous_values.get(device_address, {}).get(bacnet_obj_id)

    def mark_db_written(self, device_address: str, obj_ids) -> None:
        """Mark one or more bacnet_obj_ids as successfully written to DB and store the inserted value."""
        device_data = self.previous_values.get(device_address, {})
        for obj_id in obj_ids:
            entry = device_data.get(obj_id)
            if entry and isinstance(entry, list) and len(entry) >= 9:
                entry[8] = True
                if len(entry) >= 10:
                    entry[9] = entry[2]  # capture present_value at time of DB write
                else:
                    entry.append(entry[2])

    # Special key stored at the device level (not a BACnet obj_id)
    _HEARTBEAT_KEY = '__heartbeat__'

    def is_heartbeat_due(self, device_address: str, measured_time: str) -> bool:
        """
        Return True when the global heartbeat interval has elapsed since the
        last full (all-points) insert for this device.
        Returns True on the very first call so an initial snapshot is written.
        """
        last_time = self.previous_values.get(device_address, {}).get(self._HEARTBEAT_KEY)
        if last_time is None:
            return True
        return self._time_exceeded(last_time, measured_time, self.heartbeat_minutes)

    def mark_heartbeat(self, device_address: str, measured_time: str) -> None:
        """Record the time of the last full (all-points) insert for this device."""
        if device_address not in self.previous_values:
            self.previous_values[device_address] = {}
        self.previous_values[device_address][self._HEARTBEAT_KEY] = measured_time

    # ── private helpers ──────────────────────────────────────────────────

    def _handle_object_name(
        self,
        device_address: str,
        bacnet_obj_id: str,
        object_name: str,
        measured_time: str,
    ) -> bool:
        eqp_details = processEquipmentCode(
            object_name, tblNameLength=self.table_name_length
        )
        myprint('Eqp Param details: {}'.format(eqp_details))

        valid = eqp_details.get('inputValid', False)
        p_name = eqp_details['p_name'] if valid and 'p_name' in eqp_details else object_name
        e_id = eqp_details['e_id'] if valid and 'e_id' in eqp_details else object_name
        eqp_table_name = eqp_details['eqp_tableName'] if valid and 'eqp_tableName' in eqp_details else ''

        pv = self.previous_values
        if device_address not in pv:
            pv[device_address] = {
                bacnet_obj_id: [object_name, measured_time, None, p_name, '', e_id, eqp_table_name, '', False, None]
            }
            return False

        if bacnet_obj_id not in pv[device_address]:
            pv[device_address][bacnet_obj_id] = [
                object_name, measured_time, None, p_name, '', e_id, eqp_table_name, '', False, None
            ]
            return False

        entry = pv[device_address][bacnet_obj_id]
        if entry[0] == '':
            entry[0] = object_name
            entry[3] = p_name
            entry[5] = e_id
            entry[6] = eqp_table_name
        elif entry[0] != object_name:
            myprint('Conflict in ObjectName: {} {} currentName-{} newName-{}'.format(
                device_address, bacnet_obj_id, entry[0], object_name
            ))
        return False  # objectName updates never trigger CoV

    def _handle_present_value(
        self,
        device_address: str,
        bacnet_obj_id: str,
        present_value: Any,
        measured_time: str,
        param_type: str,
    ) -> bool:
        pv = self.previous_values

        # First time we see this device or object — seed the record.
        # Seed entry[2] with the actual present_value (not None) so that the
        # next cycle's CoV check uses the real baseline.  The heartbeat path
        # writes all points on the first cycle, so there is no need to force a
        # CoV write by leaving entry[2] as None; doing so causes every point to
        # appear as "changed" on cycle 2 and produces duplicate DB rows.
        if device_address not in pv:
            pv[device_address] = {
                bacnet_obj_id: ['', measured_time, present_value, '', '', '', '', measured_time, False, None]
            }
            return False

        if bacnet_obj_id not in pv[device_address]:
            pv[device_address][bacnet_obj_id] = [
                '', measured_time, present_value, '', '', '', '', measured_time, False, None
            ]
            return False

        entry = pv[device_address][bacnet_obj_id]
        entry[7] = measured_time  # always track last fetched time
        found_cov = False

        if param_type == 'analog':
            if self._delta_greater(entry[2], present_value, self.threshold_fraction):
                found_cov = True
                entry[1] = measured_time
            entry[2] = present_value  # always update for real-time web display

        elif param_type in ('binary', 'multiState'):
            if (
                entry[2] != present_value
            ):
                found_cov = True
                entry[1] = measured_time
            entry[2] = present_value  # always update for real-time web display

        else:
            printTrace(
                'Unexpected CoV Request: {} {} prop-presentValue val-{} type-{}'.format(
                    device_address, bacnet_obj_id, present_value, param_type
                )
            )

        return found_cov

    # ── static helpers ───────────────────────────────────────────────────

    @staticmethod
    def _delta_greater(a: float, b: float, delta: float) -> bool:
        try:
            return abs(float(a) - float(b)) > abs(float(a) * delta)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _time_exceeded(t1: str, t2: str, threshold_minutes: float) -> bool:
        fmt = '%Y-%m-%d %H:%M:%S.%f'
        try:
            elapsed = (
                datetime.strptime(t2, fmt) - datetime.strptime(t1, fmt)
            ).total_seconds()
            return elapsed >= threshold_minutes * 60
        except (ValueError, TypeError):
            return False
