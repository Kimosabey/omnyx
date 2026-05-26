"""
PointListStore — thread-safe owner of all per-device state.

Replaces:
  - The global `gl_point_list` (list of [addr, points, optional_prev_values])
  - The global `names_ready` flag
  - The per-device previous_values stored inside gl_point_list[0][i][2]

This is the single source of truth for which device/point list to read
and what CoV state has been accumulated.
"""
from __future__ import annotations

import threading
from typing import Iterator, Tuple


class PointListStore:
    """
    Encapsulates the two-phase point list:
      _rpm_list  — value reads  (was gl_point_list[0])
      _name_list — name reads   (was gl_point_list[1])

    After the first successful batch the store is "names ready" and
    subsequent batches use _rpm_list exclusively.
    """

    def __init__(
        self,
        rpm_list: list,   # list of [addr, rpm_args_list] or [addr, rpm_args_list, prev_values]
        name_list: list,  # list of [addr, name_args_list]
        names_ready: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._rpm_list = rpm_list
        self._name_list = name_list
        self._names_ready = names_ready

    # ── names_ready flag ────────────────────────────────────────────────

    @property
    def names_ready(self) -> bool:
        with self._lock:
            return self._names_ready

    def mark_names_ready(self) -> None:
        with self._lock:
            self._names_ready = True

    # ── per-device previous_values (CoV state) ──────────────────────────

    def get_previous_values(self, list_index: int) -> dict:
        """Return the current CoV state dict for the device at list_index."""
        with self._lock:
            entry = self._rpm_list[list_index]
            return entry[2] if len(entry) >= 3 else {}

    def save_previous_values(self, list_index: int, previous_values: dict) -> None:
        """
        Write back updated CoV state after a successful read cycle.
        Mirrors ThreadSupervisor.run() lines 1009-1012 in the original.
        """
        with self._lock:
            entry = self._rpm_list[list_index]
            if len(entry) >= 3:
                entry[2] = previous_values
            else:
                entry.append(previous_values)

    # ── batch iteration ─────────────────────────────────────────────────

    def iter_batch_entries(
        self,
        time_interval_counter: int,
        allow_multiple_sampling_rates: bool,
        default_interval_seconds: int,
    ) -> Iterator[Tuple[str, list, dict, int]]:
        """
        Yield (addr, points, previous_values, list_index) for every device
        that should be read in this cycle, applying the sampling-rate filter
        when allow_multiple_sampling_rates is True.

        Mirrors the loop in processCompleteBatch() in the original script.
        """
        active = self._rpm_list if self._names_ready else self._name_list

        for idx, entry in enumerate(active):
            addr_raw = entry[0]
            points = entry[1]
            prev_vals = entry[2] if len(entry) >= 3 else {}

            addr, sampling_interval = _parse_sampling_interval(addr_raw)
            if sampling_interval == 0:
                sampling_interval = default_interval_seconds

            if allow_multiple_sampling_rates:
                trigger = (
                    time_interval_counter > 0
                    and time_interval_counter % sampling_interval == 0
                )
            else:
                trigger = True

            # During the name-resolution pass always trigger
            if not self._names_ready:
                trigger = True

            if trigger:
                yield addr_raw, points, prev_vals, idx

    # ── snapshot for web server callback ────────────────────────────────

    def get_snapshot(self) -> list:
        """
        Return a flat list of rows for the web server table view.

        HTML column order: timestamp, gl_code, ddc_id, object_name, object_id,
                           p_name, display_name, present_value, db_inserted

        record layout (from CoVChecker):
          [0] objectName (BACnet object name / full GL name)
          [1] lastCoVTime
          [2] presentValue      (always current — updated every read)
          [3] p_name
          [4] '' (unused placeholder)
          [5] e_id              (GL equipment code)
          [6] eqp_tableName     (DB table name derived from gl_code)
          [7] last_read_time
          [8] db_inserted
        """
        rows = []
        with self._lock:
            if not self._names_ready:
                return rows
            for entry in self._rpm_list:
                addr_raw = entry[0]
                addr, _ = _parse_sampling_interval(addr_raw)
                prev_vals = entry[2] if len(entry) >= 3 else {}
                device_data = prev_vals.get(addr_raw, prev_vals.get(addr, {}))
                for obj_id, record in device_data.items():
                    if not isinstance(record, list) or len(record) < 9:
                        continue
                    obj_id_str = str(obj_id)
                    obj_parts = obj_id_str.split(':', 1)
                    obj_name_part = obj_parts[0]
                    obj_id_part = obj_parts[1] if len(obj_parts) > 1 else obj_id_str
                    rows.append([
                        record[7],    # timestamp (last_read_time)
                        record[0],    # gl_code   (BACnet objectName)
                        addr,         # ddc_id    (device address)
                        obj_name_part,  # object_name (first part of obj_id before ':')
                        obj_id_part,    # object_id   (second part of obj_id after ':')
                        record[3],    # p_name
                        record[4],    # display_name
                        record[2],    # present_value (current — always updated)
                        record[8],    # db_inserted
                        record[9] if len(record) > 9 else None,  # db_inserted_value
                    ])
        return rows


# ── module-level helper ────────────────────────────────────────────────────

def _parse_sampling_interval(addr_raw: str, separator: str = '@') -> Tuple[str, int]:
    """
    Split 'ip:port@interval' into ('ip:port', interval_seconds).
    Returns interval=0 when not specified (caller applies the default).
    Mirrors getSamplingInterval() in the original script.
    """
    parts = addr_raw.split(separator)
    if len(parts) > 2:
        return addr_raw, 0
    if len(parts) == 2:
        if parts[1].isnumeric():
            return parts[0], int(parts[1])
    return parts[0], 0
