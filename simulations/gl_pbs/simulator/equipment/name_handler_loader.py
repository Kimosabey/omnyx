"""
name_handler_loader — NameHandlerLoader

Reads data/eqp_name_handling.csv and creates BACnet objects
using the gl_code column directly as objectName (name-handler approach).

CSV columns:
  ddc_id, obj_type, obj_id, eqp, gl_param_name, display_name, gl_code, skip

The gl_code is used as the BACnet objectName so that the PBS
bacnet_reader (USE_OBJECT_NAME_HANDLER=True) can match returned
object names directly to GL codes without any remapping layer.
"""
from __future__ import annotations

import csv
import logging
from typing import Optional, Set, Tuple

from glDASLibrary import getHexString, getRandomAnalogInput

from simulator.equipment.registry import EquipmentRegistry
from simulator.objects.writable_objects import BACnetObjectFactory, get_random_binary_value

logger = logging.getLogger(__name__)

_BINARY_TYPES = frozenset({'binaryInput', 'binaryOutput', 'binaryValue'})


class NameHandlerLoader:
    """
    Loads BACnet objects from eqp_name_handling.csv.

    Each non-skipped row becomes one BACnet object:
      - objectIdentifier = (obj_type, obj_id)
      - objectName       = gl_code  ← name handler key
      - description      = display_name

    Args:
        registry: EquipmentRegistry to populate.
        ddc_id:   Filter to only load rows for this DDC (case-insensitive).
                  Pass None to load all DDC rows into a single device.
    """

    def __init__(
        self,
        registry: EquipmentRegistry,
        ddc_id: Optional[str] = None,
    ) -> None:
        self._registry = registry
        self._ddc_id = ddc_id.upper() if ddc_id else None

    # ── public ────────────────────────────────────────────────────────────────

    def load(self, csv_file: str = 'data/eqp_name_handling.csv') -> None:
        """Read the CSV and populate the registry with BACnet objects."""
        obj_name_set: Set[str] = set()
        obj_id_set: Set[str] = set()
        loaded = 0
        filtered = 0
        skipped_flag = 0

        try:
            with open(csv_file, newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header

                for line in reader:
                    if not line:
                        continue

                    ddc_id     = line[0].strip() if len(line) > 0 else ''
                    obj_type   = line[1].strip() if len(line) > 1 else ''
                    obj_id_str = line[2].strip() if len(line) > 2 else ''
                    eqp        = line[3].strip() if len(line) > 3 else ''
                    param_name = line[4].strip() if len(line) > 4 else ''
                    display    = line[5].strip() if len(line) > 5 else ''
                    gl_code    = line[6].strip() if len(line) > 6 else ''
                    skip_flag  = line[7].strip() if len(line) > 7 else ''

                    if not all((ddc_id, obj_type, obj_id_str, gl_code)):
                        continue

                    if skip_flag:
                        skipped_flag += 1
                        continue

                    if self._ddc_id and ddc_id.upper() != self._ddc_id:
                        filtered += 1
                        continue

                    ok = self._load_row(
                        ddc_id, obj_type, obj_id_str, eqp,
                        param_name, display, gl_code,
                        obj_name_set, obj_id_set,
                    )
                    if ok:
                        loaded += 1

        except Exception:
            logger.exception('NameHandlerLoader: error reading %s', csv_file)

        logger.info(
            'NameHandlerLoader: csv=%s  loaded=%d  filtered=%d  skip_flagged=%d',
            csv_file, loaded, filtered, skipped_flag,
        )

    # ── private ───────────────────────────────────────────────────────────────

    def _load_row(
        self,
        ddc_id: str,
        obj_type: str,
        obj_id_str: str,
        eqp: str,
        param_name: str,
        display_name: str,
        gl_code: str,
        obj_name_set: Set[str],
        obj_id_set: Set[str],
    ) -> bool:
        try:
            obj_id = int(obj_id_str)
        except ValueError:
            logger.warning(
                'NameHandlerLoader: invalid obj_id %r for gl_code=%s — skipping',
                obj_id_str, gl_code,
            )
            return False

        # BACnet (obj_type, obj_id) must be unique per device
        id_key = '{}:{}'.format(obj_type, obj_id)
        if id_key in obj_id_set:
            logger.warning(
                'NameHandlerLoader: duplicate BACnet object %s (gl_code=%s) — skipping',
                id_key, gl_code,
            )
            return False
        obj_id_set.add(id_key)

        if gl_code in obj_name_set:
            logger.warning(
                'NameHandlerLoader: duplicate gl_code %s — skipping', gl_code,
            )
            return False
        obj_name_set.add(gl_code)

        bacnet_obj = self._make_object(obj_type, obj_id, gl_code, display_name, param_name)
        if bacnet_obj is None:
            return False

        # Store in registry:
        #   eqp_type = equipment type code (e.g. 'BA', 'C0', 'A1')
        #   eqp_id   = 2-digit hex of the equipment instance number extracted
        #              from gl_code positions 9-10 (decimal → hex)
        #              e.g. 'GL 01 00 01 C0 0 001' → decimal 1 → hex '01'
        #                   'GL 01 00 10 C0 0 001' → decimal 10 → hex '0a'
        eqp_type = eqp.upper() if eqp else 'UNKNOWN'
        raw_index = gl_code[9:11] if len(gl_code) > 10 else '00'
        try:
            eqp_id = getHexString(int(raw_index), 2)
        except ValueError:
            eqp_id = '00'

        self._registry.ensure_type(eqp_type)
        eqp_entry = self._registry.get_equipment(eqp_type, eqp_id) or {}
        if 'OtherDetails' not in eqp_entry:
            eqp_entry['OtherDetails'] = {
                'EQUIPMENT_ID': eqp_id,   # 2-digit hex, e.g. '01', '0a'
                'DDC_ID': ddc_id,
            }

        # Key by gl_param_name so all instances of the same equipment type
        # share the same column names in the web dashboard table.
        # (GL codes differ per instance — e.g. GL 01 00 01 BA … vs GL 01 00 02 BA …
        #  — so using gl_code as key breaks the summary table's column alignment.)
        eqp_entry[param_name] = bacnet_obj
        self._registry.add_equipment(eqp_type, eqp_id, eqp_entry)
        return True

    def _make_object(
        self,
        obj_type: str,
        obj_id: int,
        gl_code: str,
        display_name: str,
        param_name: str,
    ):
        """
        Create a writable BACnet object.

        objectName is set to gl_code so that a BACnet reader using the
        name-handler approach can resolve the object name to a GL code
        directly, without any post-read remapping.
        """
        is_binary = obj_type in _BINARY_TYPES
        low, high = _param_range(param_name)

        pv = get_random_binary_value() if is_binary else getRandomAnalogInput(low, high)

        spec = {
            'objId':         obj_id,
            'objType':       obj_type,
            'objName':       gl_code,        # ← name handler: GL code as object name
            'description':   display_name,
            'presentValue':  pv,
            'units':         'noUnits',
            'lowLimit':      low,
            'highLimit':     high,
            'activeText':    'active',
            'inactiveText':  'inactive',
        }
        return BACnetObjectFactory.create_from_object_spec(spec)


# ── helpers ────────────────────────────────────────────────────────────────────

def _param_range(param_name: str) -> Tuple[float, float]:
    """Return (low, high) simulation defaults based on param name patterns."""
    p = param_name.lower()
    if 'temp' in p or '_sat_' in p or '_rat_' in p:
        return 15.0, 35.0
    if 'humidity' in p or '_rh_' in p or 'percent_rh' in p:
        return 20.0, 90.0
    if 'pressure' in p or '_dpt_' in p:
        return 0.0, 20.0
    if 'vfd' in p or 'speed' in p:
        return 0.0, 60.0
    if 'vlv' in p or 'valve' in p:
        return 0.0, 100.0
    if '_pwr_' in p or 'power' in p:
        return 0.0, 500.0
    if '_avg_current_' in p or 'current' in p:
        return 0.0, 100.0
    if '_avg_voltage_' in p or 'voltage' in p:
        return 200.0, 480.0
    if 'run_hrs' in p or 'hours' in p:
        return 0.0, 10000.0
    if 'energy' in p:
        return 0.0, 9999.0
    if 'load' in p:
        return 0.0, 100.0
    if 'flow' in p:
        return 0.0, 1000.0
    return 0.0, 100.0
