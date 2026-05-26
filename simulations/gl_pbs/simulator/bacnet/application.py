"""
application — SimulatorApplication: the BACnet application for the plant simulator.

SRP: Handles BACnet protocol requests (Who-Is/I-Am, ReadRange, etc.).
     Does not manage equipment state or HTTP serving.

DIP: Receives the LocalDeviceObject and address at construction;
     no global variables.

Port of MyApplication in bacnet_simulator.py.
"""
from __future__ import annotations

import logging
import sys

from bacpypes.app import BIPSimpleApplication
from bacpypes.apdu import IAmRequest, ReadRangeACK, WhoIsRequest
from bacpypes.constructeddata import Array, List, SequenceOfAny
from bacpypes.debugging import ModuleLogger, bacpypes_debugging
from bacpypes.errors import DecodingError, ExecutionError, RejectException
from bacpypes.service.cov import ChangeOfValueServices
from bacpypes.service.object import ReadWritePropertyMultipleServices

logger = logging.getLogger(__name__)
_debug = 0
_log = ModuleLogger(globals())


@bacpypes_debugging
class SimulatorApplication(
    BIPSimpleApplication,
    ReadWritePropertyMultipleServices,
    ChangeOfValueServices,
):
    """
    BACnet application for the plant simulator.

    Handles incoming BACnet messages (Who-Is/I-Am, ReadRange) and forwards
    them to the base class.  No equipment state is held here.

    Port of MyApplication.
    """

    def __init__(self, device, address: str) -> None:
        if _debug:
            SimulatorApplication._debug('__init__ %r %r', device, address)
        BIPSimpleApplication.__init__(self, device, address)
        self._request = None

    def request(self, apdu):
        if _debug:
            SimulatorApplication._debug('request %r', apdu)
        if isinstance(apdu, WhoIsRequest):
            self._request = apdu
        BIPSimpleApplication.request(self, apdu)

    def indication(self, apdu):
        if _debug:
            SimulatorApplication._debug('indication %r', apdu)

        if not self._request:
            if _debug:
                SimulatorApplication._debug('    - no pending request')

        elif isinstance(apdu, IAmRequest):
            device_type, device_instance = apdu.iAmDeviceIdentifier
            if device_type != 'device':
                raise DecodingError('invalid object type')

            low = self._request.deviceInstanceRangeLowLimit
            high = self._request.deviceInstanceRangeHighLimit
            if (low is not None and device_instance < low) or \
               (high is not None and device_instance > high):
                pass
            else:
                sys.stdout.write('pduSource = ' + repr(apdu.pduSource) + '\n')
                sys.stdout.write('iAmDeviceIdentifier = ' + str(apdu.iAmDeviceIdentifier) + '\n')
                sys.stdout.write('maxAPDULengthAccepted = ' + str(apdu.maxAPDULengthAccepted) + '\n')
                sys.stdout.write('segmentationSupported = ' + str(apdu.segmentationSupported) + '\n')
                sys.stdout.write('vendorID = ' + str(apdu.vendorID) + '\n')
                sys.stdout.flush()

        BIPSimpleApplication.indication(self, apdu)

    def response(self, apdu):
        if _debug:
            SimulatorApplication._debug('response %r', apdu)
        BIPSimpleApplication.response(self, apdu)

    def confirmation(self, apdu):
        if _debug:
            SimulatorApplication._debug('confirmation %r', apdu)
        BIPSimpleApplication.confirmation(self, apdu)

    def do_ReadRangeRequest(self, apdu):
        """Handle a ReadRange request on a trend-log object."""
        if _debug:
            SimulatorApplication._debug('do_ReadRangeRequest %r', apdu)

        obj_id = apdu.objectIdentifier
        obj = self.get_object_id(obj_id)
        if not obj:
            raise ExecutionError(errorClass='object', errorCode='unknownObject')

        datatype = obj.get_datatype(apdu.propertyIdentifier)
        if not (
            issubclass(datatype, List)
            or (
                apdu.propertyArrayIndex is not None
                and issubclass(datatype, Array)
                and issubclass(datatype.subtype, List)
            )
        ):
            raise ExecutionError(errorClass='property', errorCode='propertyIsNotAList')

        value = obj.ReadProperty(apdu.propertyIdentifier, apdu.propertyArrayIndex)
        if value is None:
            raise ExecutionError(errorClass='property', errorCode='unknownProperty')

        if not any((apdu.range.byPosition, apdu.range.bySequenceNumber, apdu.range.byTime)):
            raise RejectException('missingRequiredParameter')

        resp = ReadRangeACK(context=apdu)
        resp.objectIdentifier = obj_id
        resp.propertyIdentifier = apdu.propertyIdentifier
        resp.propertyArrayIndex = apdu.propertyArrayIndex
        resp.resultFlags = [1, 1, 0]
        resp.itemCount = len(value)
        resp.itemData = SequenceOfAny()
        resp.itemData.cast_in(datatype(value))

        self.response(resp)
