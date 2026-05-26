"""
loader — EquipmentLoader: reads deployment JSON / site CSV and populates
         an EquipmentRegistry with instantiated BACnet objects.

SRP: Only responsible for loading configuration and creating objects.
     No HTTP, no BACnet I/O, no recurring tasks.
DIP: Receives EquipmentRegistry and codebook dicts via constructor.

Consolidated from:
    loadDeploymentDetails(), loadSiteObjectDetails(),
    prepareParamObjects(), getSiteSpecificObjectID(),
    prepareEquipmentObjects(), addChildDeploymentObjects(),
    addMyObjects(), makeSiteObject()
in bacnet_simulator.py.
"""
from __future__ import annotations

import csv
import json
import logging
from typing import Dict, List, Optional

from glDASLibrary import getDeepObject, getHexString, getMyRandomMultiStateValue, getRandomAnalogInput, printTrace

from simulator.equipment.registry import EquipmentRegistry
from simulator.objects.writable_objects import BACnetObjectFactory, get_random_binary_value

logger = logging.getLogger(__name__)

_OBJECT_TYPE_CODES: Dict[str, str] = {
    'PARAM_OBJ': '0',
    'TRENDLOG_OBJ': '1',
    'ALARM_OBJ': 'A',
    'CHILD_OBJ': 'C',
    'CHILD_ALARM': 'E',
}

_ANALOG_TYPES = frozenset({'analogInput', 'analogOutput', 'analogValue'})
_BINARY_TYPES = frozenset({'binaryInput', 'binaryOutput', 'binaryValue'})


class EquipmentLoader:
    """
    Loads equipment deployment details from JSON and/or CSV config files
    and populates the given EquipmentRegistry with instantiated BACnet objects.
    """

    def __init__(
        self,
        registry: EquipmentRegistry,
        eqp_param_objects: dict,
        eqp_type_name_to_code: dict,
        use_full_gl_code: bool = True,
    ) -> None:
        self._registry = registry
        self._eqp_param_objects = eqp_param_objects
        self._eqp_type_name_to_code = eqp_type_name_to_code
        self._use_full_gl_code = use_full_gl_code

    # ── public loaders ─────────────────────────────────────────────────────────

    def load_deployment_details(
        self,
        deployment_file: str = './data/CBDeploymentDetails.json',
        gls_file: str = './data/GLSDeploymentDetails.json',
    ) -> None:
        """
        Port of loadDeploymentDetails().
        Reads JSON deployment config and creates all parent + child equipment objects.
        """
        with open(deployment_file) as f:
            eqp_details = json.load(f)

        if self._use_full_gl_code:
            with open(gls_file) as f:
                gls_details = json.load(f)
            specs = gls_details['Equipment_Specs']
        else:
            specs = eqp_details['Equipment_Specs']

        self._registry.operation_specs = specs
        self._registry.param_ids_now = dict(specs['Start_Param_IDs'])
        self._registry.trend_log_ids_now = dict(specs['Start_TrendLog_IDs'])

        for eqp_name_raw, eqp_list in eqp_details.items():
            if eqp_name_raw == 'Equipment_Specs':
                continue

            eqp_type = eqp_name_raw.upper()
            self._registry.ensure_type(eqp_type)

            for eqp_dtls in eqp_list:
                self._load_parent_equipment(eqp_type, eqp_dtls, eqp_details)

        logger.info('Loaded equipment types: %s', list(self._registry.types()))

    def load_site_objects(
        self,
        site_io_summary_file: str = 'siteEqpIOSummary.csv',
        separator: str = ',',
        with_header: bool = True,
    ) -> None:
        """
        Port of loadSiteObjectDetails().
        Reads a site-specific CSV and creates BACnet objects from it.
        """
        obj_name_set: set = set()
        obj_id_set: set = set()

        try:
            with open(site_io_summary_file, 'r') as f:
                reader = csv.reader(f, delimiter=separator)
                if with_header:
                    next(reader)

                for line in reader:
                    if not line:
                        continue
                    self._load_site_row(line, obj_name_set, obj_id_set)

        except Exception:
            logger.exception('load_site_objects: error reading %s', site_io_summary_file)

        logger.info('Site objects loaded. Equipment types: %s', list(self._registry.types()))

    # ── private: deployment loading helpers ────────────────────────────────────

    def _load_parent_equipment(
        self, eqp_type: str, eqp_dtls: dict, eqp_details: dict,
    ) -> None:
        """Creates objects for one equipment group (and its children if any)."""
        n_meters = eqp_dtls.get('noOfEqps', 0)
        prefix = '{} {}'.format(
            getHexString(int(eqp_dtls['ddcId']), 2),
            getHexString(int(eqp_dtls.get('parentId', 0)), 2),
        )
        text_prefix = getHexString(int(eqp_dtls.get('ddcId', 0)), 2)
        parent_id = int(eqp_dtls.get('parentId', 0))
        channel = getHexString(parent_id, 2)

        eqp_type_id = (
            self._eqp_type_name_to_code[eqp_type]
            if self._use_full_gl_code
            else eqp_dtls.get('eqpTypeId', 0)
        )

        start_equip_ids = eqp_details['Equipment_Specs'].get('Start_Equipment_IDs', {})
        startid_eqp = len(self._registry.get_type(eqp_type)) + int(
            start_equip_ids.get(eqp_type, 0)
        )

        object_type = 'PARAM_OBJ' if parent_id == 0 else 'CHILD_OBJ'

        eqp_objs = self._prepare_equipment_objects(
            n_meters=n_meters, gl='GL', prefix=prefix,
            text_prefix=text_prefix, channel=channel,
            eqp_type_id=eqp_type_id, parent_eqp_id=parent_id,
            meter_start_id=startid_eqp, startid_eqp=startid_eqp,
            eqp_type=eqp_type, object_type=object_type, per_eqp=True,
        )

        for myid, myobjs in eqp_objs.items():
            eqp_id_label = 'GL {} {} {}'.format(prefix, myid, eqp_type_id)
            equipment = self._make_object_dict(myobjs)
            equipment['OtherDetails'] = {'EQUIPMENT_ID': eqp_id_label}
            self._registry.add_equipment(eqp_type, myid, equipment)

            if 'childEqps' in eqp_dtls:
                self._load_child_equipment(
                    eqp_type, myid, eqp_dtls['childEqps'],
                    start_equip_ids, prefix,
                )

    def _load_child_equipment(
        self,
        parent_eqp_type: str,
        parent_id_hex: str,
        child_dtls: dict,
        start_equip_ids: dict,
        parent_prefix: str,
    ) -> None:
        """Creates child equipment objects (e.g. VAVs under an AHU)."""
        child_eqp_name = child_dtls.get('eqpTypeName')
        if not child_eqp_name:
            return

        self._registry.ensure_type(child_eqp_name)
        ch_start_id = int(start_equip_ids.get(child_eqp_name, 0))

        child_objs = self._add_child_deployment_objects(
            child_dtls, int(parent_id_hex, 16), child_eqp_name, ch_start_id,
        )

        ch_prefix = '{} {}'.format(
            getHexString(int(child_dtls.get('ddcId', 0)), 2), parent_id_hex,
        )
        ch_type_id = (
            self._eqp_type_name_to_code[child_eqp_name]
            if self._use_full_gl_code
            else child_dtls.get('eqpTypeId', 0)
        )

        for ch_id, ch_obj_list in child_objs.items():
            ch_eqp_id = 'GL {} {} {}'.format(ch_prefix, ch_id, ch_type_id)
            ch_equipment = self._make_object_dict(ch_obj_list)
            ch_equipment['OtherDetails'] = {'EQUIPMENT_ID': ch_eqp_id}
            self._registry.add_equipment(child_eqp_name, ch_id, ch_equipment)

            # Record child reference on parent
            parent = self._registry.get_equipment(parent_eqp_type, parent_id_hex)
            if parent is not None:
                child_map = parent['OtherDetails'].setdefault('ChildEqps', {})
                child_map.setdefault(child_eqp_name, set()).add(ch_id)

    def _add_child_deployment_objects(
        self,
        child_dtls: dict,
        parent_id_int: int,
        child_eqp_name: str,
        ch_eqp_start_id: int = 0,
    ) -> dict:
        """Port of addChildDeploymentObjects()."""
        n_meters = child_dtls.get('noOfChildEqpsPerParent', 0)
        prefix = '{} {}'.format(
            getHexString(int(child_dtls.get('ddcId', 0)), 2),
            getHexString(parent_id_int, 2),
        )
        text_prefix = getHexString(int(child_dtls.get('ddcId', 0)), 2)
        channel = getHexString(parent_id_int, 2)

        eqp_type_id = (
            self._eqp_type_name_to_code[child_eqp_name]
            if self._use_full_gl_code
            else child_dtls.get('eqpTypeId', 0)
        )

        count = self._registry.count_of_type(child_eqp_name)
        startid_eqp = count + ch_eqp_start_id if ch_eqp_start_id else count + 1

        return self._prepare_equipment_objects(
            n_meters=n_meters, gl='GL', prefix=prefix,
            text_prefix=text_prefix, channel=channel,
            eqp_type_id=eqp_type_id, parent_eqp_id=parent_id_int,
            meter_start_id=startid_eqp, startid_eqp=startid_eqp,
            eqp_type=child_eqp_name, object_type='CHILD_OBJ', per_eqp=True,
        )

    # ── private: site CSV loading helpers ──────────────────────────────────────

    def _load_site_row(
        self, line: list, obj_name_set: set, obj_id_set: set,
    ) -> None:
        """Parse one CSV row and add the resulting BACnet object to the registry."""
        (s_ddc_id, s_obj_type, s_obj_id, s_eqp_name,
         s_eqp_id, s_param_name, s_param_full_name, s_gl_code) = line

        if self._registry.site_ddc_id is None:
            self._registry.site_ddc_id = s_ddc_id
        elif self._registry.site_ddc_id != s_ddc_id:
            logger.warning('Multiple DDC IDs — ignoring %s, keeping %s', s_ddc_id, self._registry.site_ddc_id)
            return

        if not s_eqp_name:
            s_eqp_name = s_gl_code[12:14].lower()

        eqp_index = s_gl_code[9:11].lower()
        self._registry.ensure_type(s_eqp_name)

        duplicate = False
        id_key = '{}:{}'.format(s_obj_type, s_obj_id)
        if id_key in obj_id_set:
            logger.warning('Duplicate object ID: %s', id_key)
            duplicate = True
        else:
            obj_id_set.add(id_key)

        if s_gl_code in obj_name_set:
            logger.warning('Duplicate GL code: %s', s_gl_code)
            duplicate = True
        else:
            obj_name_set.add(s_gl_code)

        eqp_entry = self._registry.get_equipment(s_eqp_name, eqp_index) or {}
        if 'OtherDetails' not in eqp_entry:
            eqp_entry['OtherDetails'] = {'EQUIPMENT_ID': s_eqp_id}

        if s_param_name not in eqp_entry:
            site_obj = BACnetObjectFactory.create_from_site_spec(
                s_obj_type, s_obj_id, s_gl_code, s_param_name,
                s_eqp_name, self._eqp_param_objects,
            )
            if site_obj is not None and not duplicate:
                eqp_entry[s_param_name] = site_obj
                self._registry.add_equipment(s_eqp_name, eqp_index, eqp_entry)
            else:
                logger.warning('Skipping param %s for eqp %s/%s', s_param_name, s_eqp_name, eqp_index)
        else:
            logger.warning('Duplicate parameter %s in %s/%s', s_param_name, s_eqp_name, eqp_index)

    # ── private: object preparation helpers ────────────────────────────────────

    def _prepare_param_objects(
        self, eqp_type: str, parent_id: int = 0, param_bytes: int = 3,
    ) -> List[dict]:
        """Port of prepareParamObjects()."""
        myparams = (
            self._eqp_param_objects[eqp_type]['Equipment_Parameters'].values()
            if self._use_full_gl_code
            else self._eqp_param_objects[eqp_type]
        )
        result = []
        analog_types = {'analogInput', 'analogOutput', 'analogValue',
                        'binaryInput', 'binaryOutput', 'binaryValue', 'multiStateValue'}
        for i, x in enumerate(myparams):
            obj = {'objName': getHexString(parent_id * 16 + i, param_bytes), 'description': ''}
            if isinstance(x, str):
                obj['description'] = x
            elif isinstance(x, dict):
                obj['description'] = x.get('name', '')
                if x.get('units'):
                    obj['units'] = x['units']
                if x.get('type') in analog_types:
                    obj['objType'] = x['type']
                for key in ('writable', 'rangeLow', 'rangeHigh', 'numberOfStates', 'ObjectID'):
                    if key in x:
                        obj[key] = x[key]
                if 'rangeLow' in x:
                    obj['lowLimit'] = x['rangeLow']
                if 'rangeHigh' in x:
                    obj['highLimit'] = x['rangeHigh']
            result.append(obj)
        return result

    def _get_site_specific_object_id(
        self, eqp_type: str, site_param: dict, e_index_0_based: int,
    ) -> Optional[int]:
        """Port of getSiteSpecificObjectID()."""
        specs = self._registry.operation_specs
        if 'COUNT_OF_EQUIPMENT_PARAMETERS' not in specs:
            return None
        count_map = specs['COUNT_OF_EQUIPMENT_PARAMETERS']
        if eqp_type not in count_map:
            return None
        base_id = site_param.get('ObjectID')
        if base_id is None or base_id == '':
            return None
        return count_map[eqp_type] * e_index_0_based + base_id

    def _prepare_equipment_objects(
        self,
        n_meters: int,
        gl: str,
        prefix: str,
        text_prefix: str,
        channel: str,
        eqp_type_id,
        parent_eqp_id: int,
        meter_start_id: int,
        startid_eqp: int,
        eqp_type: str,
        object_type: str = 'PARAM_OBJ',
        per_eqp: bool = True,
    ) -> dict:
        """Port of prepareEquipmentObjects()."""
        param_objects = self._prepare_param_objects(eqp_type, parent_eqp_id)
        result: dict = {}

        for meter_i in range(n_meters):
            meter_code = getHexString(meter_i + meter_start_id, 2)
            result[meter_code] = []

            base_name = '{} {} {} {} {}'.format(gl, text_prefix, channel, meter_code, eqp_type_id)

            for param in param_objects:
                is_alarm = 'alarm' in param['description'].lower()
                if is_alarm:
                    obj_code = (
                        _OBJECT_TYPE_CODES['ALARM_OBJ']
                        if object_type == 'PARAM_OBJ'
                        else _OBJECT_TYPE_CODES['CHILD_ALARM']
                    )
                else:
                    obj_code = _OBJECT_TYPE_CODES[object_type]

                site_id = self._get_site_specific_object_id(eqp_type, param, meter_i)
                if site_id is not None:
                    self._registry.param_ids_now[eqp_type] = site_id

                obj_spec: dict = {
                    'objId': self._registry.param_ids_now.get(eqp_type, 0),
                    'objType': param.get('objType', 'analogValue'),
                    'objName': '{} {} {}'.format(base_name, obj_code, param['objName']),
                    'description': param['description'],
                    'units': 'degreesCelsius',
                }
                if eqp_type in self._registry.param_ids_now:
                    self._registry.param_ids_now[eqp_type] += 1

                low = float(param.get('rangeLow', 80.0))
                high = float(param.get('rangeHigh', 120.0))
                obj_spec['lowLimit'] = low
                obj_spec['highLimit'] = high

                obj_type_str = obj_spec['objType']
                if obj_type_str in _BINARY_TYPES:
                    obj_spec['presentValue'] = get_random_binary_value()
                elif obj_type_str in _ANALOG_TYPES:
                    obj_spec['presentValue'] = getRandomAnalogInput(low, high)
                elif obj_type_str == 'multiStateValue':
                    obj_spec['numberOfStates'] = param.get('numberOfStates', 2)
                    obj_spec['presentValue'] = getMyRandomMultiStateValue(obj_spec['numberOfStates'])
                else:
                    import random
                    obj_spec['presentValue'] = round(random.uniform(low, high), 2)

                result[meter_code].append(obj_spec)

                # Paired trend-log object
                tl_id = self._registry.trend_log_ids_now.get(eqp_type, 0)
                if eqp_type in self._registry.trend_log_ids_now:
                    self._registry.trend_log_ids_now[eqp_type] += 1

                tl_spec = {
                    'objId': tl_id,
                    'objType': 'trendLog',
                    'objName': '{} {} {}'.format(base_name, _OBJECT_TYPE_CODES['TRENDLOG_OBJ'], param['objName']),
                    'description': param['description'],
                    'presentValue': obj_spec['presentValue'],
                    'units': obj_spec['units'],
                }
                result[meter_code].append(tl_spec)

        return result

    def _make_object_dict(self, obj_list: list) -> dict:
        """
        Port of addMyObjects(makedict=True).
        Creates BACnet objects from spec dicts and returns {description: obj}.
        """
        obj_dict: dict = {}
        for spec in obj_list:
            if spec.get('objType') == 'trendLog':
                continue  # trend logs are added separately in main()
            obj = BACnetObjectFactory.create_from_object_spec(spec)
            if obj is not None:
                obj_dict[spec['description']] = obj
        return obj_dict
