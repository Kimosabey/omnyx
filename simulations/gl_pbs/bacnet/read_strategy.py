"""
BACnet Read Strategies — Open/Closed Principle implementation.

AbstractReadStrategy defines the interface; concrete strategies
(RPMReadStrategy, SingleReadStrategy) implement it.  New read modes
can be added without touching ReadPointListThread.

Extracted from ReadPointListThread:
  RPMReadStrategy   ← prepareBACnetAccessSpecs + readMultipleProperties
                       + _get_RPM_ACK_Dict + multiple_properties_received
  SingleReadStrategy ← runReadPointsNoRPM
"""
from __future__ import annotations

import abc
from inspect import currentframe, getframeinfo

from bacpypes.apdu import (
    AbortPDU,
    PropertyIdentifier,
    PropertyReference,
    ReadAccessSpecification,
    ReadPropertyMultipleACK,
    ReadPropertyMultipleRequest,
    ReadPropertyRequest,
    RejectPDU,
)
from bacpypes.constructeddata import Array
from bacpypes.core import deferred
from bacpypes.iocb import IOCB
from bacpypes.object import get_datatype
from bacpypes.pdu import Address
from bacpypes.primitivedata import ObjectIdentifier, Unsigned

from glDASLibrary import getstrTimeNow, myerror, myprint

SUCCESS = 0
RPM_NOT_SUPPORTED = 2  # device explicitly rejected the RPM service


def _is_rpm_rejection(error) -> bool:
    """Return True when *error* is an explicit BACnet rejection of RPM.

    A RejectPDU means the device does not recognise the service at all.
    An AbortPDU with buffer-overflow or segmentation-not-supported means
    the RPM response was too large for the device to send.
    Plain timeouts (exceptions) are NOT treated as rejections — the caller
    should keep retrying with a longer timeout instead.
    """
    if isinstance(error, RejectPDU):
        return True
    if isinstance(error, AbortPDU):
        reason = str(
            getattr(error, 'apduAbortRejectReason', '')
            or getattr(error, 'apduRejectReason', '')
        )
        return reason in ('buffer-overflow', 'segmentation-not-supported',
                          'unrecognized-service')
    return False


class AbstractReadStrategy(abc.ABC):
    """
    Interface for BACnet read strategies.

    OCP: The thread coordinator never checks 'if rpm else ...' — it
    calls strategy.prepare() then strategy.execute() regardless of mode.

    LSP: Both concrete strategies mutate point_values and thread_dump
    in the same way and return the same SUCCESS sentinel.
    """

    @abc.abstractmethod
    def prepare(self, point_list: list, point_values: dict) -> None:
        """
        Pre-flight initialisation (e.g. build RPM access specs).
        Called once before execute().
        """

    @abc.abstractmethod
    def execute(
        self,
        bacnet_app,          # BIPSimpleApplication
        device_address: str,
        timeout: float,
        point_values: dict,  # mutated in-place with results
        thread_dump: dict,   # mutated in-place with timestamps
    ) -> int:
        """
        Perform the BACnet read.
        Returns SUCCESS (0) on full success, non-zero on any failure.
        """


# ── RPM strategy ───────────────────────────────────────────────────────────

class RPMReadStrategy(AbstractReadStrategy):
    """
    Executes ReadPropertyMultiple (RPM).

    Ports: prepareBACnetAccessSpecs + readMultipleProperties
           + _get_RPM_ACK_Dict + multiple_properties_received
    """

    def __init__(self, use_object_name_handler: bool = False) -> None:
        self._use_object_name_handler = use_object_name_handler
        self._read_access_spec_list: list = []

    # ── AbstractReadStrategy ──────────────────────────────────────────

    def prepare(self, point_list: list, point_values: dict) -> None:
        """Build RPM access specs.  Port of prepareBACnetAccessSpecs()."""
        myprint('RPMReadStrategy.prepare — point_list length:{} first5:{}'.format(
            len(point_list), point_list[:5]
        ))
        self._point_list_raw = point_list  # kept for to_single_pairs() fallback
        self._read_access_spec_list = self._build_access_specs(
            point_list, point_values
        )

    def execute(
        self,
        bacnet_app,
        device_address: str,
        timeout: float,
        point_values: dict,
        thread_dump: dict,
    ) -> int:
        """Port of readMultipleProperties()."""
        if not self._read_access_spec_list:
            myerror('RPMReadStrategy.execute — empty spec list for {}'.format(device_address))
            return 1

        myprint('RPMReadStrategy.execute — sending RPM to {} ({} specs)'.format(
            device_address, len(self._read_access_spec_list)
        ))
        try:
            # Strip any '@sampling_interval' suffix that PointListStore may
            # include in addr_raw (e.g. "192.168.0.104:2001@30").
            clean_address = device_address.split('@')[0]
            request = ReadPropertyMultipleRequest(
                listOfReadAccessSpecs=self._read_access_spec_list
            )
            request.pduDestination = Address(clean_address)

            iocb = IOCB(request)
            iocb.set_timeout(timeout)
            deferred(bacnet_app.request_io, iocb)

            thread_dump['device_requested'] = getstrTimeNow()
            iocb.wait()

            if iocb.ioResponse:
                thread_dump['device_responded'] = getstrTimeNow()
                return self._handle_response(iocb, device_address, point_values)

            if iocb.ioError:
                thread_dump['device_errored'] = getstrTimeNow()
                if _is_rpm_rejection(iocb.ioError):
                    myerror('RPM-REJECTED:{} from:{} — will fallback to ReadProperty'.format(
                        iocb.ioError, device_address
                    ))
                    return RPM_NOT_SUPPORTED
                myerror('RPM-ERROR:{} timeout:{} from:{}'.format(
                    iocb.ioError, timeout, device_address
                ))

        except Exception as err:
            fi = getframeinfo(currentframe())
            myerror('Exception-{} in file-{} function-{} line-{}'.format(
                err, fi.filename, fi.function, fi.lineno
            ))

        return 1  # failure

    # ── private helpers ───────────────────────────────────────────────

    def _build_access_specs(self, args: list, point_values: dict) -> list:
        """Port of prepareBACnetAccessSpecs()."""
        spec_list = []
        try:
            i = 0
            while i < len(args):
                obj_id = ObjectIdentifier(args[i]).value
                obj_key = '{}:{}'.format(obj_id[0], obj_id[1])
                if obj_key not in point_values:
                    point_values[obj_key] = {}
                i += 1

                prop_refs = []
                while i < len(args):
                    prop_id = args[i]
                    if prop_id not in PropertyIdentifier.enumerations:
                        break
                    i += 1

                    if prop_id not in ('all', 'required', 'optional'):
                        datatype = get_datatype(obj_id[0], prop_id)
                        if not datatype:
                            raise ValueError('invalid property for object type')

                    prop_ref = PropertyReference(propertyIdentifier=prop_id)
                    if (i < len(args)) and args[i].isdigit():
                        prop_ref.propertyArrayIndex = int(args[i])
                        i += 1

                    prop_refs.append(prop_ref)
                    if prop_id not in point_values[obj_key]:
                        point_values[obj_key][prop_id] = {}
                    if prop_ref.propertyArrayIndex is not None:
                        point_values[obj_key][prop_id].setdefault(
                            'propertyArray', {}
                        )[prop_ref.propertyArrayIndex] = ''

                if not prop_refs:
                    myerror('Requesting Read with {}'.format(args))
                    raise ValueError('provide at least one property')

                spec_list.append(
                    ReadAccessSpecification(
                        objectIdentifier=obj_id,
                        listOfPropertyReferences=prop_refs,
                    )
                )

            if not spec_list:
                raise RuntimeError('at least one read access specification required')

        except Exception as err:
            fi = getframeinfo(currentframe())
            myerror('Exception-{} in file-{} function-{} line-{}'.format(
                err, fi.filename, fi.function, fi.lineno
            ))

        return spec_list

    def to_single_pairs(self) -> list:
        """Convert parsed RPM access specs to (obj_id_str, prop_id) pairs.

        Called by ReadPointListThread when it needs to fall back to
        ReadProperty after an RPM rejection.  prepare() must have been
        called first.
        """
        pairs = []
        for spec in self._read_access_spec_list:
            oid = spec.objectIdentifier       # ('analogInput', 1)
            obj_str = '{}:{}'.format(oid[0], oid[1])
            for ref in spec.listOfPropertyReferences:
                pairs.append((obj_str, ref.propertyIdentifier))
        return pairs

    def _handle_response(
        self, iocb, device_address: str, point_values: dict
    ) -> int:
        """Port of multiple_properties_received() + _get_RPM_ACK_Dict()."""
        if iocb.ioError:
            myerror('RPM-ERROR:{} from:{}'.format(iocb.ioError, device_address))
            return 1

        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyMultipleACK):
            myerror('Not an RPM ACK from {}'.format(device_address))
            return 1

        cnt_objects_success = 0
        for result in apdu.listOfReadAccessResults:
            obj_id = result.objectIdentifier
            obj_key = '{}:{}'.format(obj_id[0], obj_id[1])
            cnt_props_success = 0

            for element in result.listOfResults:
                prop_id = element.propertyIdentifier
                prop_array_index = element.propertyArrayIndex
                read_result = element.readResult

                if read_result.propertyAccessError is not None:
                    continue  # leave property in point_values as-is

                prop_value = read_result.propertyValue
                datatype = get_datatype(obj_id[0], prop_id)

                if not datatype:
                    myerror('Unknown datatype for object {} property {}'.format(obj_key, prop_id))
                    continue  # skip — do not count as success, do not store empty entry

                if issubclass(datatype, Array) and prop_array_index is not None:
                    value = prop_value.cast_out(
                        Unsigned if prop_array_index == 0 else datatype.subtype
                    )
                    point_values[obj_key][prop_id].setdefault(
                        'propertyArray', {}
                    )[prop_array_index] = value
                else:
                    value = prop_value.cast_out(datatype)
                    point_values[obj_key][prop_id]['propertyValue'] = value

                point_values[obj_key][prop_id]['objectType'] = obj_id[0]
                cnt_props_success += 1

            if cnt_props_success == len(result.listOfResults):
                cnt_objects_success += 1

        total = len(apdu.listOfReadAccessResults)
        myprint('RPM ACK from {} — {}/{} objects succeeded'.format(
            device_address, cnt_objects_success, total
        ))

        if cnt_objects_success == total:
            return SUCCESS

        myerror('Received:{} Expected:{}'.format(cnt_objects_success, total))
        return 1


# ── Single-property strategy ───────────────────────────────────────────────

class SingleReadStrategy(AbstractReadStrategy):
    """
    Reads BACnet points one at a time using ReadProperty.
    Used for DDC/PLC controllers that do not support ReadPropertyMultiple.

    Port of ReadPointListThread.runReadPointsNoRPM().
    """

    def prepare(self, point_list: list, point_values: dict) -> None:
        """Pre-initialise point_values keys from the (obj_id, prop_id) list."""
        for obj_id_str, prop_id in point_list:
            key = str(obj_id_str)
            if key not in point_values:
                point_values[key] = {}
            if prop_id not in point_values[key]:
                point_values[key][prop_id] = {}

    def execute(
        self,
        bacnet_app,
        device_address: str,
        timeout: float,
        point_values: dict,
        thread_dump: dict,
    ) -> int:
        any_success = False

        clean_address = device_address.split('@')[0]
        for obj_id_str, prop_id in self._point_list:
            obj_id = ObjectIdentifier(obj_id_str).value
            obj_key = '{}:{}'.format(obj_id[0], obj_id[1])

            request = ReadPropertyRequest(
                destination=Address(clean_address),
                objectIdentifier=obj_id,
                propertyIdentifier=prop_id,
            )
            iocb = IOCB(request)
            iocb.set_timeout(timeout)
            deferred(bacnet_app.request_io, iocb)

            thread_dump['device_requested'] = getstrTimeNow()
            iocb.wait()

            if iocb.ioResponse:
                thread_dump['device_responded'] = getstrTimeNow()
                apdu = iocb.ioResponse
                datatype = get_datatype(
                    apdu.objectIdentifier[0], apdu.propertyIdentifier
                )
                if not datatype:
                    myerror('Unknown datatype for {}'.format(obj_key))
                    # Remove the placeholder so downstream code never sees an empty entry
                    point_values.get(obj_key, {}).pop(prop_id, None)
                    if obj_key in point_values and not point_values[obj_key]:
                        del point_values[obj_key]
                    continue

                if (
                    issubclass(datatype, Array)
                    and apdu.propertyArrayIndex is not None
                ):
                    value = apdu.propertyValue.cast_out(
                        Unsigned
                        if apdu.propertyArrayIndex == 0
                        else datatype.subtype
                    )
                else:
                    value = apdu.propertyValue.cast_out(datatype)

                point_values[obj_key][prop_id]['objectType'] = apdu.objectIdentifier[0]
                point_values[obj_key][prop_id]['propertyValue'] = value
                any_success = True

            elif iocb.ioError:
                thread_dump['device_errored'] = getstrTimeNow()
                # Remove the placeholder to prevent downstream KeyError on missing propertyValue
                point_values.get(obj_key, {}).pop(prop_id, None)
                if obj_key in point_values and not point_values[obj_key]:
                    del point_values[obj_key]

        return SUCCESS if any_success else 1

    # SingleReadStrategy.prepare needs the point_list later in execute —
    # store it for use by execute().
    def prepare(self, point_list: list, point_values: dict) -> None:  # type: ignore[override]
        self._point_list = point_list
        for obj_id_str, prop_id in point_list:
            key = str(obj_id_str)
            if key not in point_values:
                point_values[key] = {}
            if prop_id not in point_values[key]:
                point_values[key][prop_id] = {}
