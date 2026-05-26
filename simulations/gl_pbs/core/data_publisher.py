"""
DataPublisher — builds and sends BACnet read-data notifications.

SRP: Only responsible for constructing notification payloads and
     posting them to the configured HTTP endpoint.

Extracted from ReadPointListThread.prepareCoVNotificationData(),
prepareNotificationData(), and the postEquipmentData() call in
postProcessResults().
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from glDASLibrary import myprint, getMyParamName, postEquipmentData, getstrTimeNow

if TYPE_CHECKING:
    from core.cov_checker import CoVChecker


class DataPublisher:
    """
    Constructs and delivers data notification payloads.

    Notify modes (mirror notifyReadData in the original config):
      'ALL_RM'       — post all read values every cycle
      'ONLY_COV'     — post only changed values
      'DONOT_NOTIFY' — skip posting entirely
    """

    def __init__(
        self,
        post_url: str,
        notify_mode: str,
        web_post_timeout_secs: float,
    ) -> None:
        self.post_url = post_url
        self.notify_mode = notify_mode
        self.web_post_timeout_secs = web_post_timeout_secs

    # ── payload builders ─────────────────────────────────────────────────

    def build_cov_payload(
        self,
        thread_id: str,
        device_address: str,
        point_values: dict,
        cov_checker: 'CoVChecker',
        measured_time: str,
        check_cov: bool = True,
    ) -> Optional[dict]:
        """
        Compute CoV for every point and build the notification body.

        Returns a dict  {"CoVNotification": {...}, "CoVPoints": {...}}
        when at least one CoV was found, or None otherwise.

        Port of ReadPointListThread.prepareCoVNotificationData().
        """
        get_param_type = lambda p: (
            'analog'
            if p.lower() in ('analoginput', 'analogoutput', 'analogvalue')
            else 'binary'
        )

        mybody = {
            'myuuid': thread_id,
            'measured_time': measured_time,
            device_address: {},
        }
        cov_points: Optional[dict] = None
        cov_available = False

        myprint(
            'Call to build_cov_payload - Address: {} Points: {}'.format(
                device_address, list(point_values.keys())
            )
        )

        for obj_id, props in point_values.items():
            # objectName and presentValue are processed independently — an RPM cycle
            # may return both for the same object (e.g. when useObjectNameHandler=True).
            if 'objectName' in props and 'propertyValue' in props['objectName']:
                # objectName reads update the CoV state but never trigger a notification
                cov_checker.update(
                    device_address, obj_id, 'objectName',
                    props['objectName']['propertyValue']
                )

            if 'presentValue' in props and 'propertyValue' in props['presentValue']:
                obj_type = props['presentValue'].get('objectType', '')
                param_type = get_param_type(str(obj_type))
                cov_found = cov_checker.update(
                    device_address, obj_id, 'presentValue',
                    props['presentValue']['propertyValue'],
                    measured_time,
                    param_type,
                )
                if cov_found:
                    record = cov_checker.get_record(device_address, obj_id)
                    obj_name = record[0] if record else ''
                    myprint(
                        'build_cov_payload - obj-{} props-{} objName-{}'.format(
                            obj_id, props, obj_name
                        )
                    )
                    if obj_name:
                        mybody[device_address][obj_name] = (
                            getMyParamName(obj_name),
                            props['presentValue']['propertyValue'],
                            obj_id,
                        )
                    else:
                        mybody[device_address][obj_id] = (
                            props['presentValue']['propertyValue']
                        )
                    cov_available = True
                    if cov_points is None:
                        cov_points = {}
                    cov_points[obj_id] = props

        if cov_available:
            return {
                'CoVNotification': json.loads(json.dumps(mybody)),
                'CoVPoints': cov_points,
            }
        return None

    def build_all_data_payload(
        self,
        thread_id: str,
        device_address: str,
        point_values: dict,
        cov_checker: 'CoVChecker',
        measured_time: str,
        names_ready: bool,
    ) -> Optional[dict]:
        """
        Build a payload containing all present-value readings.
        Returns None when names have not yet been resolved.

        Port of ReadPointListThread.prepareNotificationData().
        """
        if not names_ready:
            return None

        mybody = {
            'myuuid': thread_id,
            'measured_time': measured_time,
            device_address: {},
        }
        for obj_id, props in point_values.items():
            if 'presentValue' not in props or 'propertyValue' not in props['presentValue']:
                continue
            record = cov_checker.get_record(device_address, obj_id)
            obj_name = record[0] if record else ''
            mybody[device_address][obj_name] = (
                getMyParamName(obj_name),
                props['presentValue']['propertyValue'],
                obj_id,
            )
        return json.loads(json.dumps(mybody))

    # ── delivery ─────────────────────────────────────────────────────────

    def post(self, payload: dict) -> None:
        """Send a notification payload to the configured HTTP endpoint."""
        if payload is not None:
            postEquipmentData(self.post_url, payload, self.web_post_timeout_secs)
