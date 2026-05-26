"""
writable_objects — custom writable BACnet object types + object factory.

SRP: Defines the 7 writable BACnet object classes and a factory that
     creates BACnet object instances from plain object-spec dicts.

OCP: New BACnet types can be added without modifying the factory;
     register_object_type handles the protocol layer automatically.

Extracted from the top-level class definitions and makeSiteObject() /
addMyObjects() functions in bacnet_simulator.py.
"""
from __future__ import annotations

import logging
import random
from typing import Optional

from bacpypes.basetypes import BinaryPV, PriorityArray, TimeStamp
from bacpypes.object import (
    AnalogInputObject,
    AnalogOutputObject,
    AnalogValueObject,
    BinaryInputObject,
    BinaryOutputObject,
    BinaryValueObject,
    MultiStateOutputObject,
    MultiStateValueObject,
    ReadableProperty,
    WritableProperty,
    register_object_type,
)
from bacpypes.primitivedata import Real, Unsigned

from glDASLibrary import getDeepObject, getRandomAnalogInput

logger = logging.getLogger(__name__)


# ── Writable BACnet object type definitions ────────────────────────────────────

@register_object_type
class WritableAnalogValueObject(AnalogValueObject):
    properties = [
        WritableProperty('presentValue', Real),
        WritableProperty('highLimit', Real),
        WritableProperty('lowLimit', Real),
        WritableProperty('lastCommandTime', TimeStamp),
        ReadableProperty('priorityArray', PriorityArray),
    ]


@register_object_type
class WritableBinaryValueObject(BinaryValueObject):
    properties = [
        WritableProperty('presentValue', BinaryPV),
        ReadableProperty('priorityArray', PriorityArray),
        WritableProperty('lastCommandTime', TimeStamp),
    ]


@register_object_type
class WritableMultiStateValueObject(MultiStateValueObject):
    properties = [
        WritableProperty('presentValue', Unsigned),
        WritableProperty('numberOfStates', Unsigned),
        ReadableProperty('priorityArray', PriorityArray),
        WritableProperty('lastCommandTime', TimeStamp),
    ]


@register_object_type
class WritableAnalogInputObject(AnalogInputObject):
    properties = [
        WritableProperty('presentValue', Real),
        WritableProperty('highLimit', Real),
        WritableProperty('lowLimit', Real),
        WritableProperty('lastCommandTime', TimeStamp),
        ReadableProperty('priorityArray', PriorityArray),
    ]


@register_object_type
class WritableBinaryInputObject(BinaryInputObject):
    properties = [
        WritableProperty('presentValue', BinaryPV),
        ReadableProperty('priorityArray', PriorityArray),
        WritableProperty('lastCommandTime', TimeStamp),
    ]


@register_object_type
class WritableAnalogOutputObject(AnalogOutputObject):
    properties = [
        WritableProperty('presentValue', Real),
        WritableProperty('highLimit', Real),
        WritableProperty('lowLimit', Real),
        WritableProperty('lastCommandTime', TimeStamp),
        ReadableProperty('priorityArray', PriorityArray),
    ]


@register_object_type
class WritableBinaryOutputObject(BinaryOutputObject):
    properties = [
        WritableProperty('presentValue', BinaryPV),
        ReadableProperty('priorityArray', PriorityArray),
        WritableProperty('lastCommandTime', TimeStamp),
    ]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_random_binary_value(return_bool: bool = False):
    """Returns a random binary value as 'active'/'inactive' or bool."""
    value = random.random() >= 0.5
    if return_bool:
        return value
    return 'active' if value else 'inactive'


def get_bacnet_class_name(obj) -> str:
    """Returns a string label for the concrete type of a BACnet object."""
    class_map = {
        WritableAnalogValueObject: 'WritableAnalogValueObject',
        WritableBinaryValueObject: 'WritableBinaryValueObject',
        WritableAnalogInputObject: 'WritableAnalogInputObject',
        WritableBinaryInputObject: 'WritableBinaryInputObject',
        WritableAnalogOutputObject: 'WritableAnalogOutputObject',
        WritableBinaryOutputObject: 'WritableBinaryOutputObject',
        WritableMultiStateValueObject: 'WritableMultiStateValueObject',
    }
    for cls, name in class_map.items():
        if isinstance(obj, cls):
            return name
    return 'Unknown'


# ── Object factory ─────────────────────────────────────────────────────────────

class BACnetObjectFactory:
    """
    Creates writable BACnet object instances from specification dicts.

    Two entry points:
      create_from_site_spec   — for CSV-loaded site objects (makeSiteObject)
      create_from_object_spec — for JSON-loaded deployment objects (addMyObjects)
    """

    _DEFAULT_LOW = 0.0
    _DEFAULT_HIGH = 100.0
    _DEFAULT_COV = 0.5

    @classmethod
    def create_from_site_spec(
        cls,
        obj_type,
        obj_id: int,
        obj_name: str,
        description: str,
        eqp_type: str,
        eqp_param_objects: dict,
    ) -> Optional[object]:
        """
        Port of makeSiteObject().
        Looks up range/unit overrides in eqp_param_objects, then instantiates.
        """
        low = cls._DEFAULT_LOW
        high = cls._DEFAULT_HIGH
        unit = 'noUnits'
        active, inactive = 'active', 'inactive'

        # Apply safe hard-coded limits based on param name patterns.
        # These serve as sensible defaults even when CBParameters has no entry.
        desc_lower = description.lower()
        if '_temp_' in desc_lower or desc_lower.endswith('_temp') or 'temp' in desc_lower:
            high = 38.0
        elif '_dpt_' in desc_lower or desc_lower == 'dpt':
            high = 1.0
        elif 'humidity' in desc_lower or '_rh_' in desc_lower:
            high = 100.0
        elif 'frequency' in desc_lower or '_freq_' in desc_lower:
            low, high = 45.0, 60.0
        elif 'voltage' in desc_lower:
            high = 480.0
        elif '_pf_' in desc_lower or 'power_factor' in desc_lower:
            high = 1.0
        elif 'flow' in desc_lower:
            high = 1000.0

        cb_obj = getDeepObject(eqp_param_objects, [eqp_type, 'Equipment_Parameters', description])
        if cb_obj is None:
            # eqp_type from site CSV is a hex code (e.g. 'B0'); eqp_param_objects is
            # keyed by type-name ('Chiller').  Scan for a matching EqpTypeCode.
            eqp_type_lower = eqp_type.lower()
            for entry in eqp_param_objects.values():
                if isinstance(entry, dict) and entry.get('EqpTypeCode', '').lower() == eqp_type_lower:
                    cb_obj = entry.get('Equipment_Parameters', {}).get(description)
                    break
        if cb_obj is not None:
            low = float(cb_obj.get('rangeLow', low))
            high = float(cb_obj.get('rangeHigh', high))
            if cb_obj.get('units'):
                unit = cb_obj['units']

        pv_analog = getRandomAnalogInput(low, high)
        pv_binary = get_random_binary_value()

        spec = {
            'objId': int(obj_id),
            'objType': str(obj_type),
            'objName': obj_name,
            'description': description,
            'presentValue': pv_analog,
            'units': unit,
            'lowLimit': low,
            'highLimit': high,
            'activeText': active,
            'inactiveText': inactive,
        }
        if any(str(obj_type) in s for s in ['binaryInput', 'binaryOutput', 'binaryValue', '3', '4', '5']):
            spec['presentValue'] = pv_binary
        return cls._instantiate(spec)

    @classmethod
    def create_from_object_spec(cls, spec: dict) -> Optional[object]:
        """Port of the per-object creation block in addMyObjects()."""
        return cls._instantiate(spec)

    @classmethod
    def _instantiate(cls, x: dict) -> Optional[object]:
        """
        Core factory: maps objType string to a concrete writable object class.
        Returns None (with a logged warning) for unknown types.
        """
        obj_type = str(x.get('objType', 'analogValue')).strip()
        obj_id = int(x['objId'])
        obj_name = x['objName']
        desc = x.get('description', '')
        units = x.get('units', 'noUnits')
        pv = x.get('presentValue', 0)
        low = float(x.get('lowLimit', cls._DEFAULT_LOW))
        high = float(x.get('highLimit', cls._DEFAULT_HIGH))
        active = x.get('activeText', 'True')
        inactive = x.get('inactiveText', 'False')

        try:
            if obj_type in ('0', 'analogInput'):
                return WritableAnalogInputObject(
                    objectIdentifier=('analogInput', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=float(pv), covIncrement=cls._DEFAULT_COV,
                    units=units, lowLimit=low, highLimit=high,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type in ('1', 'analogOutput'):
                return WritableAnalogOutputObject(
                    objectIdentifier=('analogOutput', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=float(pv), covIncrement=cls._DEFAULT_COV,
                    units=units, lowLimit=low, highLimit=high,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type in ('2', 'analogValue'):
                return WritableAnalogValueObject(
                    objectIdentifier=('analogValue', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=float(pv), covIncrement=cls._DEFAULT_COV,
                    units=units, lowLimit=low, highLimit=high,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type in ('3', 'binaryInput'):
                return WritableBinaryInputObject(
                    objectIdentifier=('binaryInput', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=pv, activeText=active, inactiveText=inactive,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type in ('4', 'binaryOutput'):
                return WritableBinaryOutputObject(
                    objectIdentifier=('binaryOutput', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=pv, activeText=active, inactiveText=inactive,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type in ('5', 'binaryValue'):
                return WritableBinaryValueObject(
                    objectIdentifier=('binaryValue', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=pv, activeText=active, inactiveText=inactive,
                    statusFlags=[0, 0, 0, 0],
                )
            if obj_type == 'multiStateValue':
                return WritableMultiStateValueObject(
                    objectIdentifier=('multiStateValue', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=int(pv),
                    numberOfStates=int(x.get('numberOfStates', 2)),
                )
            if obj_type == 'multiStateOutput':
                return MultiStateOutputObject(
                    objectIdentifier=('multiStateOutput', obj_id),
                    objectName=obj_name, description=desc,
                    presentValue=int(pv),
                    numberOfStates=int(x.get('numberOfStates', 2)),
                )
            logger.warning('BACnetObjectFactory: unknown objType %r — skipping', obj_type)
            return None

        except Exception as exc:
            logger.exception(
                'BACnetObjectFactory: error creating %s:%s (%s) — %s',
                obj_type, obj_id, desc, exc,
            )
            return None
