"""
application — BACnet services application for the HTTP-to-BACnet gateway.

SRP: Only handles BACnet protocol I/O (IOCB creation, callback dispatch,
     response parsing).  HTTP, queue management, and config are injected.

OCP: New services can be added as methods without altering existing ones.

DIP: ResponsePoster, SubscriptionRegistry, and the queue-resume callback
     are injected at construction.

Extracted from GLBACnetServicesApplication in bacnet_writer.py.
"""
from __future__ import annotations

import logging
import sys
import urllib.parse
from collections import OrderedDict, deque
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

from bacpypes.apdu import (
    IAmRequest,
    PropertyIdentifier,
    PropertyReference,
    ReadAccessSpecification,
    ReadPropertyACK,
    ReadPropertyMultipleACK,
    ReadPropertyMultipleRequest,
    ReadPropertyRequest,
    ReadRangeACK,
    ReadRangeRequest,
    Range, RangeByPosition, RangeBySequenceNumber, RangeByTime,
    SimpleAckPDU,
    SubscribeCOVRequest,
    TimeSynchronizationRequest,
    WhoIsRequest,
    WritePropertyRequest,
)
from bacpypes.app import BIPSimpleApplication
from bacpypes.basetypes import (
    ArrayOf, DailySchedule, DateTime, PropertyValue,
    SpecialEvent, TimeValue, CalendarEntry,
)
from bacpypes.constructeddata import Array, Any, AnyAtomic, ListOf
from bacpypes.core import deferred
from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.errors import DecodingError, ExecutionError
from bacpypes.iocb import IOCB
from bacpypes.object import get_datatype
from bacpypes.pdu import Address
from bacpypes.primitivedata import (
    Boolean, CharacterString, Date, Double, Integer,
    ObjectIdentifier, OctetString, Real, Tag, Time, Unsigned, BitString, Null,
)
from bacpypes.service.cov import ChangeOfValueServices
from bacpypes.service.object import ReadWritePropertyMultipleServices

from bacnet.service_context import ObjectListContext, ServiceContext, SubscriptionRegistry
from glObjectNameHandler import processObjectNames

if TYPE_CHECKING:
    from config.server_config import ServerConfig
    from core.response_poster import ResponsePoster

logger = logging.getLogger(__name__)
_debug = 0
_log = ModuleLogger(globals())

ArrayOfObjectIdentifier = ArrayOf(ObjectIdentifier)


@bacpypes_debugging
class BACnetServicesApplication(
    BIPSimpleApplication,
    ReadWritePropertyMultipleServices,
    ChangeOfValueServices,
):
    """
    BACnet IP application providing all gateway services.

    Services: discoverDevices, discoverObjects, readObjectProperty,
    readMultipleProperties, subscribePropertyCoV, trendLogReadRange,
    timeSyncDevice, writeObjectProperty.

    Port of GLBACnetServicesApplication with injected dependencies.
    """

    def __init__(
        self,
        device,
        ip_address: str,
        config: 'ServerConfig',
        response_poster: 'ResponsePoster',
        subscription_registry: SubscriptionRegistry,
        resume_callback: Optional[Callable] = None,
    ) -> None:
        """
        Parameters
        ----------
        device               : LocalDeviceObject
        ip_address           : Local IP address for BACnet binding.
        config               : ServerConfig (use_object_name_handler, etc.)
        response_poster      : ResponsePoster for posting service results.
        subscription_registry: SubscriptionRegistry for CoV tracking.
        resume_callback      : Called in every service completion callback
                               to resume the queue processor and dispatch
                               the next request.
        """
        BIPSimpleApplication.__init__(self, device, ip_address)
        self._config = config
        self._poster = response_poster
        self._subscriptions = subscription_registry
        self._resume = resume_callback or (lambda: None)

    # ── BIPSimpleApplication overrides ─────────────────────────────────────────

    def request(self, apdu) -> None:
        if isinstance(apdu, WhoIsRequest):
            self._request = apdu
        BIPSimpleApplication.request(self, apdu)

    def indication(self, apdu) -> None:
        if isinstance(apdu, IAmRequest):
            device_type, device_instance = apdu.iAmDeviceIdentifier
            if device_type != 'device':
                raise DecodingError('invalid object type')
            sys.stdout.write(
                'pduSource=%r iAmDeviceIdentifier=%s maxAPDU=%s seg=%s vendor=%s\n' % (
                    apdu.pduSource,
                    apdu.iAmDeviceIdentifier,
                    apdu.maxAPDULengthAccepted,
                    apdu.segmentationSupported,
                    apdu.vendorID,
                )
            )
        BIPSimpleApplication.indication(self, apdu)

    def confirmation(self, apdu) -> None:
        BIPSimpleApplication.confirmation(self, apdu)

    # ── discoverDevices ────────────────────────────────────────────────────────

    def discoverDevices(self, myreq: dict, parsed: dict) -> None:
        logger.info('discoverDevices — uuid: %s', myreq.get('request_uuid'))
        # WhoIs broadcast implementation left for future extension

    # ── discoverObjects ────────────────────────────────────────────────────────

    def discoverObjects(
        self,
        myreq: dict,
        parsed: dict,
        segmentation_supported: bool = True,
    ) -> None:
        logger.info('discoverObjects — uuid: %s', myreq.get('request_uuid'))
        device_id = ObjectIdentifier(parsed['objid']).value
        device_addr = Address(parsed['destination'])
        context = ObjectListContext(
            device_id, device_addr, myreq,
            segmentation_supported=segmentation_supported,
            response_poster=self._poster,
        )
        self._read_object_list(context)

    def _read_object_list(self, context: ObjectListContext) -> None:
        request = ReadPropertyRequest(
            destination=context.device_addr,
            objectIdentifier=context.device_id,
            propertyIdentifier='objectList',
        )

        if not context.segmentation_supported:
            if context.object_list_length == 0:
                request.propertyArrayIndex = 0
            elif len(context.object_list) < context.object_list_length:
                request.propertyArrayIndex = len(context.object_list) + 1

        iocb = IOCB(request)
        iocb.context = context
        if context.segmentation_supported:
            iocb.add_callback(self._object_list_results)
        else:
            iocb.add_callback(self._received_object_no_segmentation)
        self.request_io(iocb)

    def _received_object_no_segmentation(self, iocb) -> None:
        """Read objectList length then individual entries."""
        context: ObjectListContext = iocb.context
        if iocb.ioError:
            logger.error('_received_object_no_segmentation — error: %s', iocb.ioError)
            context.completed(iocb.ioError)
            return

        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyACK):
            context.completed(RuntimeError('read property ack expected'))
            return

        datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
        if not datatype:
            raise TypeError('unknown datatype')
        if issubclass(datatype, Array) and apdu.propertyArrayIndex is not None:
            datatype = Unsigned if apdu.propertyArrayIndex == 0 else datatype.subtype

        value = apdu.propertyValue.cast_out(datatype)
        if apdu.propertyArrayIndex == 0:
            context.object_list_length = value
        else:
            context.object_list.append(value)

        if len(context.object_list) < context.object_list_length:
            deferred(self._read_object_list, context)
        else:
            context._object_list_queue = deque(context.object_list)
            deferred(self._read_next_object, context)

    def _object_list_results(self, iocb) -> None:
        context: ObjectListContext = iocb.context
        if iocb.ioError:
            context.completed(iocb.ioError)
            return
        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyACK):
            context.completed(RuntimeError('read property ack expected'))
            return
        object_list = apdu.propertyValue.cast_out(ArrayOfObjectIdentifier)
        context.object_list = object_list
        context._object_list_queue = deque(object_list)
        deferred(self._read_next_object, context)

    def _read_next_object(self, context: ObjectListContext) -> None:
        if not context._object_list_queue:
            context.completed()
            return
        object_id = context._object_list_queue.popleft()
        request = ReadPropertyRequest(
            destination=context.device_addr,
            objectIdentifier=object_id,
            propertyIdentifier='objectName',
        )
        iocb = IOCB(request)
        iocb.context = context
        iocb.add_callback(self._object_name_results)
        self.request_io(iocb)

    def _object_name_results(self, iocb) -> None:
        context: ObjectListContext = iocb.context
        if iocb.ioError:
            context.completed(iocb.ioError)
            return
        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyACK):
            context.completed(RuntimeError('read property ack expected'))
            return
        context.object_names.append(apdu.propertyValue.cast_out(CharacterString))
        deferred(self._read_next_object, context)

    # ── readObjectProperty ─────────────────────────────────────────────────────

    def readObjectProperty(self, myreq: dict, parsed: dict) -> None:
        logger.info('readObjectProperty — uuid: %s', myreq.get('request_uuid'))
        context = ServiceContext(
            Address(parsed['destination']),
            parsed['objid'],
            http_request=myreq,
            response_poster=self._poster,
        )
        request = ReadPropertyRequest(
            destination=context.address,
            objectIdentifier=context.monitoredObjectIdentifier,
            propertyIdentifier=PropertyIdentifier(parsed['propertyId']).value,
        )
        if parsed.get('arrayindex') is not None:
            request.propertyArrayIndex = parsed['arrayindex']

        iocb = IOCB(request)
        iocb.context = context
        iocb.add_callback(self._object_property_received)
        self.request_io(iocb)

    def _object_property_received(self, iocb) -> None:
        logger.info('_object_property_received')
        self._resume()
        context: ServiceContext = iocb.context
        if iocb.ioError:
            context.completed(iocb.ioError)
            return
        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyACK):
            context.completed(RuntimeError('read property ack expected'))
            return

        if apdu.propertyIdentifier == 'presentValue':
            _, value = self._get_property_datatype_value(apdu.propertyValue)
        else:
            _, value = self._get_read_datatype_value(apdu)

        context.post_response({'propertyType': 'TBD', 'propertyValue': value})

    # ── readMultipleProperties ─────────────────────────────────────────────────

    def readMultipleProperties(self, myreq: dict, parsed: dict) -> None:
        logger.info('readMultipleProperties — uuid: %s', myreq.get('request_uuid'))
        context = ServiceContext(
            Address(parsed['destination']),
            http_request=myreq,
            response_poster=self._poster,
        )
        args = parsed['objids_propids'].split('/')

        try:
            i = 1  # skip leading empty string from split('/')
            addr = parsed['destination']
            read_access_spec_list = []

            while i < len(args):
                obj_id = ObjectIdentifier(args[i]).value
                i += 1
                prop_reference_list = []
                while i < len(args):
                    prop_id = args[i]
                    if prop_id not in PropertyIdentifier.enumerations:
                        break
                    i += 1
                    if prop_id not in ('all', 'required', 'optional'):
                        if not get_datatype(obj_id[0], prop_id):
                            raise ValueError('invalid property for object type')
                    prop_ref = PropertyReference(propertyIdentifier=prop_id)
                    if i < len(args) and args[i].isdigit():
                        prop_ref.propertyArrayIndex = int(args[i])
                        i += 1
                    prop_reference_list.append(prop_ref)

                if not prop_reference_list:
                    raise ValueError('provide at least one property')
                read_access_spec_list.append(
                    ReadAccessSpecification(
                        objectIdentifier=obj_id,
                        listOfPropertyReferences=prop_reference_list,
                    )
                )

            if not read_access_spec_list:
                raise RuntimeError('at least one read access specification required')

            request = ReadPropertyMultipleRequest(
                listOfReadAccessSpecs=read_access_spec_list,
            )
            request.pduDestination = Address(addr)

            iocb = IOCB(request)
            iocb.context = context
            iocb.set_timeout(10)
            iocb.add_callback(self._multiple_properties_received)
            self.request_io(iocb)

        except Exception as exc:
            logger.exception('readMultipleProperties exception: %s', exc)

    def _multiple_properties_received(self, iocb) -> None:
        logger.info('_multiple_properties_received')
        self._resume()
        context: ServiceContext = iocb.context
        if iocb.ioError:
            logger.error('_multiple_properties_received — error: %s', iocb.ioError)
            return
        if not iocb.ioResponse:
            return
        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadPropertyMultipleACK):
            return
        context.post_response({
            'propertyResults': self._get_rpm_ack_dict(apdu.listOfReadAccessResults)
        })

    def _get_rpm_ack_dict(self, results_list) -> list:
        """Port of _get_RPM_ACK_Dict()."""
        output = []
        for result in results_list:
            obj_id = result.objectIdentifier
            obj_entry = {
                'objectType': obj_id[0],
                'objectId': obj_id[1],
                'properties': [],
            }
            for element in result.listOfResults:
                prop_id = element.propertyIdentifier
                prop_array_index = element.propertyArrayIndex
                read_result = element.readResult
                prop_entry = {'propertyId': prop_id}
                if prop_array_index is not None:
                    prop_entry['propertyArrayIndex'] = prop_array_index
                if read_result.propertyAccessError is not None:
                    prop_entry['propertyAccessError'] = str(read_result.propertyAccessError)
                else:
                    datatype = get_datatype(obj_id[0], prop_id)
                    if not datatype:
                        value = '?'
                    elif issubclass(datatype, Array) and prop_array_index is not None:
                        value = read_result.propertyValue.cast_out(
                            Unsigned if prop_array_index == 0 else datatype.subtype
                        )
                    else:
                        value = read_result.propertyValue.cast_out(datatype)
                    prop_entry['datatype'] = read_result.propertyValue.__class__.__name__
                    prop_entry['propertyValue'] = value
                obj_entry['properties'].append(prop_entry)
            output.append(obj_entry)

        if self._config.use_object_name_handler:
            output = processObjectNames(output, {'prefixChanged': 'JL'}, [])
        return output

    # ── subscribePropertyCoV ───────────────────────────────────────────────────

    def subscribePropertyCoV(self, myreq: dict, parsed: dict) -> None:
        logger.info('subscribePropertyCoV — uuid: %s', myreq.get('request_uuid'))
        context = ServiceContext(
            Address(parsed['destination']),
            parsed['objid'],
            confirmed=parsed.get('confirmed', self._config.confirmed_subscription_cov),
            lifetime=parsed.get('lifetime', self._config.subscription_cov_lifetime),
            http_request=myreq,
            response_poster=self._poster,
            subscription_registry=self._subscriptions,
        )
        request = SubscribeCOVRequest(
            subscriberProcessIdentifier=context.subscriberProcessIdentifier,
            monitoredObjectIdentifier=context.monitoredObjectIdentifier,
        )
        request.pduDestination = context.address
        if context.issueConfirmedNotifications is not None:
            request.issueConfirmedNotifications = context.issueConfirmedNotifications
        if context.lifetime is not None:
            request.lifetime = context.lifetime

        iocb = IOCB(request)
        iocb.add_callback(self._subscription_acknowledged)
        self.request_io(iocb)

    def _subscription_acknowledged(self, iocb) -> None:
        logger.info('_subscription_acknowledged')
        self._resume()

    def do_ConfirmedCOVNotificationRequest(self, apdu) -> None:
        context = self._subscriptions.lookup(apdu.subscriberProcessIdentifier)
        if not context or apdu.pduSource != context.address:
            raise ExecutionError('services', 'unknownSubscription')
        context.cov_notification(apdu)
        self.response(SimpleAckPDU(context=apdu))

    def do_UnconfirmedCOVNotificationRequest(self, apdu) -> None:
        context = self._subscriptions.lookup(apdu.subscriberProcessIdentifier)
        if not context or apdu.pduSource != context.address:
            return
        context.cov_notification(apdu)

    # ── trendLogReadRange ──────────────────────────────────────────────────────

    def trendLogReadRange(self, myreq: dict, parsed: dict) -> None:
        logger.info('trendLogReadRange — uuid: %s', myreq.get('request_uuid'))
        try:
            context = ServiceContext(
                Address(parsed['destination']),
                parsed['objid'],
                http_request=myreq,
                response_poster=self._poster,
            )
            addr = Address(parsed['destination'])
            obj_id = ObjectIdentifier(parsed['objid']).value
            prop_id = parsed['propertyId']
            if prop_id.isdigit():
                prop_id = int(prop_id)

            datatype = get_datatype(obj_id[0], prop_id)
            if not datatype:
                raise ValueError('invalid property for object type')

            request = ReadRangeRequest(
                destination=addr, objectIdentifier=obj_id, propertyIdentifier=prop_id
            )

            raw_range = urllib.parse.unquote(parsed['indexrange'], encoding='utf-8').split()
            if raw_range:
                if raw_range[0].isdigit():
                    if not issubclass(datatype, Array):
                        raise ValueError('property is not an array')
                    request.propertyArrayIndex = int(raw_range.pop(0))
                    datatype = datatype.subtype
            if not issubclass(datatype, ListOf):
                raise ValueError('property is not a list')

            if raw_range:
                rt = raw_range.pop(0)
                if rt == 'p':
                    request.range = Range(
                        byPosition=RangeByPosition(
                            referenceIndex=int(raw_range[0]), count=int(raw_range[1])
                        )
                    )
                elif rt == 's':
                    request.range = Range(
                        bySequenceNumber=RangeBySequenceNumber(
                            referenceSequenceNumber=int(raw_range[0]), count=int(raw_range[1])
                        )
                    )
                elif rt == 't':
                    request.range = Range(
                        byTime=RangeByTime(
                            referenceTime=DateTime(
                                date=Date(raw_range[0]).value,
                                time=Time(raw_range[1]).value,
                            ),
                            count=int(raw_range[2]),
                        )
                    )
                elif rt == 'x':
                    request.range = Range()
                else:
                    raise ValueError('unknown range type: %r' % rt)

            iocb = IOCB(request)
            iocb.context = context
            iocb.add_callback(self._range_data_received)
            self.request_io(iocb)

        except Exception as exc:
            logger.exception('trendLogReadRange exception: %s', exc)

    def _range_data_received(self, iocb) -> None:
        logger.info('_range_data_received')
        self._resume()
        context: ServiceContext = iocb.context
        if iocb.ioError:
            context.completed(iocb.ioError)
            return
        if not iocb.ioResponse:
            return
        apdu = iocb.ioResponse
        if not isinstance(apdu, ReadRangeACK):
            return

        datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
        if not datatype:
            raise TypeError('unknown datatype')

        value = apdu.itemData.cast_out(datatype)
        mylist = [
            {
                'timestamp': self._timestamp_display(item.timestamp),
                'logDatum': item.logDatum.dict_contents(),
            }
            for item in value
        ]
        context.post_response(mylist)

    @staticmethod
    def _timestamp_display(ts) -> str:
        d, t = ts.date, ts.time
        return datetime(d[0] + 1900, d[1], d[2], t[0], t[1], t[2]).isoformat()

    # ── timeSyncDevice ─────────────────────────────────────────────────────────

    def timeSyncDevice(self, myreq: dict, parsed: dict) -> None:
        logger.info('timeSyncDevice — uuid: %s', myreq.get('request_uuid'))
        context = ServiceContext(
            Address(parsed['destination']),
            parsed['objid'],
            http_request=myreq,
            response_poster=self._poster,
        )
        request = TimeSynchronizationRequest(
            time=DateTime(date=Date().now().value, time=Time().now().value),
        )
        request.pduDestination = context.address
        iocb = IOCB(request)
        iocb.context = context
        self.request_io(iocb)

    # ── writeObjectProperty ────────────────────────────────────────────────────

    def writeObjectProperty(self, myreq: dict, parsed: dict) -> None:
        logger.info('writeObjectProperty — uuid: %s', myreq.get('request_uuid'))
        context = ServiceContext(
            Address(parsed['destination']),
            parsed['objid'],
            http_request=myreq,
            response_poster=self._poster,
        )

        try:
            request = WritePropertyRequest(
                destination=Address(parsed['destination']),
                objectIdentifier=ObjectIdentifier(parsed['objid']).value,
                propertyIdentifier=PropertyIdentifier(parsed['propertyId']).value,
            )

            if 'post_body' in myreq:
                value = self._prepare_value_from_post_body(myreq, parsed)
            else:
                value = self._prepare_write_value(
                    ObjectIdentifier(parsed['objid']).value,
                    parsed['propertyId'],
                    parsed['newValue'],
                    parsed.get('arrayindex'),
                )
                if parsed.get('arrayindex') is not None:
                    request.propertyArrayIndex = parsed['arrayindex']
                if parsed.get('priority') is not None:
                    request.priority = parsed['priority']

            request.propertyValue = Any()
            try:
                request.propertyValue.cast_in(value)
            except Exception as exc:
                logger.error('writeObjectProperty cast error: %s', exc)

            iocb = IOCB(request)
            iocb.context = context
            iocb.set_timeout(10)
            iocb.add_callback(self._property_write_ack_received)
            deferred(self.request_io, iocb)

        except Exception as exc:
            logger.exception('writeObjectProperty setup error: %s', exc)
            self._resume()
            status = f'Error: {exc}'
            callback = myreq.get('_status_callback')
            if callback:
                callback(status)
            context.post_response(status)

    def _property_write_ack_received(self, iocb) -> None:
        logger.info('_property_write_ack_received')
        self._resume()
        context: ServiceContext = iocb.context
        if iocb.ioResponse:
            status = 'Acknowledged' if isinstance(iocb.ioResponse, SimpleAckPDU) else 'Not-Acknowledged'
        elif iocb.ioError:
            status = f'Error: {iocb.ioError}'
        else:
            status = 'Unknown'
        callback = context.http_request.get('_status_callback') if context.http_request else None
        if callback:
            callback(status)
        context.post_response(status)

    def _prepare_write_value(self, obj_id, prop_id, value_in, indx):
        """Port of _prepareWriteValue()."""
        value = value_in
        try:
            datatype = get_datatype(obj_id[0], prop_id)
            if value == 'null':
                value = Null()
            elif issubclass(datatype, AnyAtomic):
                dtype_key, dvalue = value.split(':', 1)
                dtype_map = {
                    'b': Boolean, 'u': lambda x: Unsigned(int(x)),
                    'i': lambda x: Integer(int(x)), 'r': lambda x: Real(float(x)),
                    'd': lambda x: Double(float(x)), 'o': OctetString,
                    'c': CharacterString, 'bs': BitString,
                    'date': Date, 'time': Time, 'id': ObjectIdentifier,
                }
                value = dtype_map[dtype_key](dvalue)
            elif issubclass(datatype, Array.__class__) and indx is not None:
                value = Integer(value) if indx == 0 else datatype.subtype(value)
            elif issubclass(datatype, Real.__class__):
                value = Real(float(value))
            elif issubclass(datatype, Integer.__class__):
                value = Integer(int(value))
            elif issubclass(datatype, Unsigned.__class__):
                value = Unsigned(int(value))
            else:
                try:
                    value = datatype(value)
                except Exception:
                    value = Real(float(value))
        except Exception as exc:
            logger.error('_prepare_write_value error: %s', exc)
        return value

    def _prepare_value_from_post_body(self, httpreq: dict, parsed: dict):
        """Port of _prepareValueFromPostBody()."""
        prop_id = parsed['propertyId']
        if prop_id == 'weeklySchedule':
            default_sched = ArrayOf(DailySchedule, 7)([
                DailySchedule(daySchedule=[
                    TimeValue(time=(0, 0, 0, 0), value=Boolean(False)),
                    TimeValue(time=(12, 0, 0, 0), value=Boolean(False)),
                ])
            ] * 7)
            body = httpreq['post_body']
            if body.get('value_type') == 'BOOLEAN':
                return self._get_weekly_schedule(body, default_sched)
            return self._get_weekly_schedule(body)
        elif prop_id == 'dateList':
            return self._get_calendar_entries(httpreq['post_body'])
        logger.warning('_prepare_value_from_post_body — unhandled property: %s', prop_id)
        return None

    def _get_weekly_schedule(self, ui_schedule: dict, current=None):
        """Port of getBACnetWeeklySchedule()."""
        from datetime import time as dtime
        if current is None:
            weekly = ArrayOf(DailySchedule, 7)([
                DailySchedule(daySchedule=[
                    TimeValue(time=(0, 0, 0, 0), value=Real(0.0)),
                    TimeValue(time=(12, 0, 0, 0), value=Real(0.0)),
                ])
            ] * 7)
        else:
            weekly = current

        vtype = ui_schedule['value_type']
        if vtype == 'REAL':
            sv = Real(ui_schedule['start_value'])
            ev = Real(ui_schedule['end_value'])
        else:  # BOOLEAN
            sv = Boolean(ui_schedule['start_value'].lower() == 'on')
            ev = Boolean(ui_schedule['start_value'].lower() != 'on')

        st = dtime.fromisoformat(ui_schedule['start_time'])
        et = dtime.fromisoformat(ui_schedule['end_time'])
        day_sched = DailySchedule(daySchedule=[
            TimeValue(time=(st.hour, st.minute, st.second, st.microsecond), value=sv),
            TimeValue(time=(et.hour, et.minute, et.second, et.microsecond), value=ev),
        ])
        _DAY_MAP = {
            'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4,
            'friday': 5, 'saturday': 6, 'sunday': 7,
        }
        for day in ui_schedule.get('weekdays', []):
            idx = _DAY_MAP.get(day.lower())
            if idx:
                weekly[idx] = day_sched
        return weekly

    def _get_calendar_entries(self, ui_entries: dict, current=None):
        """Port of getBACnetCalendarEntries()."""
        entries = ListOf(CalendarEntry)([]) if current is None else current
        for s in ui_entries.get('holidays', []):
            entries.append(CalendarEntry(date=Date(s).value))
        return entries

    # ── APDU value helpers ─────────────────────────────────────────────────────

    def _get_read_datatype_value(self, apdu):
        """Port of _getReadDatatypeValue()."""
        if not isinstance(apdu, ReadPropertyACK):
            return (None, None)
        datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
        if not datatype:
            raise TypeError('unknown datatype')
        if issubclass(datatype, Array) and apdu.propertyArrayIndex is not None:
            value = apdu.propertyValue.cast_out(
                Unsigned if apdu.propertyArrayIndex == 0 else datatype.subtype
            )
        else:
            value = apdu.propertyValue.cast_out(datatype)
        return (datatype, value)

    def _get_property_datatype_value(self, property_value):
        """Port of _getProperty_DataType_Value()."""
        try:
            tag_list = property_value.tagList
        except AttributeError:
            return RuntimeError('non PropertyValue passed')

        non_app = [t for t in tag_list if t.tagClass != Tag.applicationTagClass]
        if non_app:
            raise RuntimeError('value has non-application tags')

        first = tag_list[0]
        if any(t.tagNumber != first.tagNumber for t in tag_list[1:]):
            raise RuntimeError('all tags must be the same type')

        datatype = Tag._app_tag_class[first.tagNumber]
        if not datatype:
            raise RuntimeError('unknown datatype')
        if len(tag_list) > 1:
            datatype = ArrayOf(datatype)

        value = property_value.cast_out(datatype)
        return (datatype, value)
