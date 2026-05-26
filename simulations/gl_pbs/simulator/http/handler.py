"""
handler — SimulatorHttpHandler: HTTP request handler for the plant simulator web UI.

SRP: Handles HTTP GET/POST, routes to the correct action, and returns HTML/JSON.
     Does not manage BACnet objects or equipment loading directly;
     reads state from an injected EquipmentRegistry.

DIP: Registry, my_address, and eqp_param_objects are injected via configure()
     before the TCPServer creates handler instances.

Port of GLHttpRequestHandler in bacnet_simulator.py.
"""
from __future__ import annotations

import json
import logging
import random
from typing import Optional

try:
    from urllib.parse import parse_qs, urlparse
    from http.server import SimpleHTTPRequestHandler
except ImportError:
    from urlparse import parse_qs, urlparse  # type: ignore
    from SimpleHTTPServer import SimpleHTTPRequestHandler  # type: ignore

from bacpypes.debugging import ModuleLogger, bacpypes_debugging

from glDASLibrary import getDeepObject, getHexString, getRandomAnalogInput

from simulator.equipment.registry import EquipmentRegistry
from simulator.objects.writable_objects import (
    WritableAnalogInputObject,
    WritableAnalogOutputObject,
    WritableAnalogValueObject,
    WritableBinaryInputObject,
    WritableBinaryOutputObject,
    WritableBinaryValueObject,
    WritableMultiStateValueObject,
    get_bacnet_class_name,
)

logger = logging.getLogger(__name__)
_debug = 0
_log = ModuleLogger(globals())


@bacpypes_debugging
class SimulatorHttpHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler for the plant simulator dashboard and control API.

    Class-variable injection pattern: call configure() once before creating
    the TCPServer.  Each request spawns a new handler instance that reads
    these class-level variables.

    Port of GLHttpRequestHandler.
    """

    # ── class-level injection (set once before server creation) ────────────────
    _registry: Optional[EquipmentRegistry] = None
    _my_address: Optional[str] = None
    _eqp_param_objects: dict = {}
    _web_port: Optional[int] = None

    @classmethod
    def configure(
        cls,
        registry: EquipmentRegistry,
        my_address: str,
        eqp_param_objects: dict,
        web_port: Optional[int] = None,
    ) -> None:
        cls._registry = registry
        cls._my_address = my_address
        cls._eqp_param_objects = eqp_param_objects
        cls._web_port = web_port

    # ── HTTP verbs ─────────────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if _debug:
            SimulatorHttpHandler._debug('do_GET')

        result = self._route_request(self.client_address, self.requestline, self.path)

        self.send_response(200)
        self._send_cors_headers()
        if isinstance(result, tuple) and len(result) == 2 and result[0] == 'json':
            self.send_header('Content-type', 'application/json')
            result_bytes = result[1].encode('utf-8')
        else:
            html_head = '<head><meta http-equiv="refresh" content="15"></head>'
            self.send_header('Content-type', 'text/html')
            result_bytes = (html_head + str(result)).encode('utf-8')
        self.end_headers()
        self.wfile.write(result_bytes)

    def do_POST(self) -> None:
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        post_json = json.loads(post_data)

        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        result = 'Server Post Result - {} {} {} {}'.format(
            self.client_address, self.requestline, self.path, post_json,
        )
        self.wfile.write(json.dumps(result).encode('utf-8'))

    def _send_cors_headers(self) -> None:
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    # ── request router ─────────────────────────────────────────────────────────

    def _route_request(self, client_address, requestline: str, path: str):
        """Port of processHttpRequest() — routes URL path to the correct handler."""
        link_template = ' <a href="/{}">{}</a>'
        registry = self._registry

        routes = {
            'updateEquipmentDetails': ('Change Parameter', self._update_equipment_details, True, 'HIDDEN'),
            'getPlantSnapshot':       ('Plant Snapshot',   self._get_plant_snapshot,        False),
            'getSimulatorInfo':       ('Simulator Info',   self._get_simulator_info,         False),
            'getBACnetReaderFile':    ('PBS-2 Reader File', self._get_reader_file,           False),
            'resetAllEquipment':      ('Reset Plant',      self._reset_all_equipment,        True),
            'prepareEqpTypeSummary':  ('Equipment Details', self._equipment_type_summary,    True, 'HIDDEN'),
        }

        raw_params = parse_qs(urlparse(path).query)
        params: dict = {}
        for qp, qv in raw_params.items():
            if qp == 'mytype' and registry and qv[0] in registry.get_all():
                params['Equipment_Type'] = qv[0]
            elif qp == 'id':
                params['Equipment_Id'] = getHexString(int(qv[0]), 2)
            else:
                params[qp] = qv[0]

        response = ''
        show_template = True
        for url_key, route_def in routes.items():
            if url_key in path:
                response = route_def[1](params)
                show_template = route_def[2] if len(route_def) > 2 else True
                break

        if show_template:
            response = self._default_dashboard(client_address, requestline, path) + response
            response += 'Other Useful Links:'
            for url_key, route_def in routes.items():
                if len(route_def) > 3 and route_def[3] == 'HIDDEN':
                    continue
                response += link_template.format(url_key, route_def[0])

        return response

    # ── endpoint handlers ──────────────────────────────────────────────────────

    def _default_dashboard(self, client_address, requestline: str, path: str) -> str:
        """Port of processHttpRequestDefault()."""
        registry = self._registry
        html = (
            '<a href="/"><img alt="Graylinx Simulator" height="32px" '
            'src="https://ibms.graylinx.ai/static/media/graylinxlogo2.1ad063c6.png"></a>'
        )
        html += '<a href="/getEquipmentDetails?mytype=CHILLER&id=1">Dashboard</a>'
        html += ' — {} with Request — {} <p>Path-{}'.format(client_address, requestline, path)

        raw_params = parse_qs(urlparse(path).query)
        if 'mytype' in raw_params and 'id' in raw_params:
            html += self._equipment_detail(raw_params['mytype'][0], raw_params['id'][0])

        html += '<h4>Equipment Summary</h4>'
        tbody = ''
        tline = '<tr><td><a href="/getEquipmentDetails?mytype={}&id={}">{}</a></td><td>{}</td><td>{}</td></tr>'
        summary_link = '<a href="/prepareEqpTypeSummary?mytype={}">{}</a>'

        if registry:
            for eqp_type, instances in registry.get_all().items():
                if instances:
                    first_id = int(list(instances.keys())[0], 16)
                    tbody += tline.format(
                        eqp_type, first_id, eqp_type,
                        len(instances),
                        summary_link.format(eqp_type, 'ALL ' + eqp_type),
                    )

        return html + '<table border="all"><tr><th>Type</th><th>Count</th><th>Details</th></tr>{}</table>'.format(tbody)

    def _equipment_type_summary(self, params: dict) -> str:
        """Port of prepareEqpTypeSummary()."""
        registry = self._registry
        eqp_type = params.get('Equipment_Type', '')
        if not registry or eqp_type not in registry.get_all():
            return '<h4>Invalid Request — {}</h4>'.format(eqp_type)

        param_columns = None
        if eqp_type == 'CHILLER':
            param_columns = 'CH_On_Off,CH_Run_SS,CH_AM_SS,CH_Out_Vlv_On_Off,CH_Out_Vlv_On_Off_SS,CD_In_Vlv_On_Off,CD_In_Vlv_On_Off_SS'.split(',')

        row_tpl = '<tr><td>{}</td><td>{}</td>{}</tr>'
        id_link = '<a href="/getEquipmentDetails?mytype={}&id={}">{}</a>'
        cell = '<td>{}</td>'
        rows = ''

        for eqp_id, eqp_data in registry.get_type(eqp_type).items():
            display_params = param_columns or [k for k in eqp_data if k != 'OtherDetails']
            if not param_columns:
                # Emit header once
                header_cells = ''.join(cell.format(p) for p in display_params)
                rows += row_tpl.format('Eqp', 'Eqp-ID', header_cells)
                param_columns = display_params  # use same columns for subsequent rows

            param_cells = ''.join(
                cell.format(eqp_data[p].presentValue if p in eqp_data else '')
                for p in display_params
            )
            eqp_display_id = eqp_data['OtherDetails']['EQUIPMENT_ID']
            num_id = int('0x' + str(eqp_id), 16)
            rows += row_tpl.format(id_link.format(eqp_type, num_id, eqp_id), eqp_display_id, param_cells)

        return '<h4>Summary — <u>{}</u></h4><table border="all">{}</table>'.format(eqp_type, rows)

    def _equipment_detail(self, eqp_type: str, eqp_id: str) -> str:
        """Port of prepareEqpData()."""
        registry = self._registry
        if not registry:
            return ''

        row_tpl = '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'
        header = row_tpl.format('Class', 'objType', 'objId', 'objName', 'description', 'lastCommandTime', 'presentValue', 'Change')

        hex_id = getHexString(int(eqp_id), 2)
        eqp_data = registry.get_equipment(eqp_type, hex_id)
        if not eqp_data:
            return '<h4>Not found: {} {}</h4>'.format(eqp_type, eqp_id)

        # Form template: submits newValue typed by the user under the correct param key.
        # Uses GET so the router can match 'updateEquipmentDetails' in the path.
        form_tpl = (
            '<form style="display:inline" action="/updateEquipmentDetails" method="get">'
            '<input type="hidden" name="mytype" value="{eqp_type}">'
            '<input type="hidden" name="id" value="{eqp_id}">'
            '<input type="hidden" name="description" value="{param_name}">'
            '<input type="text" name="newValue" value="{suggested}" size="10">'
            '&nbsp;<button type="submit">Change</button>'
            '</form>'
        )

        rows = header
        for param_name, obj in eqp_data.items():
            if param_name == 'OtherDetails':
                continue
            obj_type_str = obj.objectIdentifier[0]
            if any(obj_type_str in s for s in ['binaryInput', 'binaryOutput', 'binaryValue']):
                suggested = 'inactive' if str(obj.presentValue) == 'active' else 'active'
            elif any(obj_type_str in s for s in ['analogInput', 'analogOutput', 'analogValue']):
                suggested = '{:.2f}'.format(obj.presentValue * (0.8 + 0.4 * random.random()))
            else:
                suggested = str(obj.presentValue)

            change_form = form_tpl.format(
                eqp_type=eqp_type, eqp_id=eqp_id,
                param_name=param_name, suggested=suggested,
            )

            rows += row_tpl.format(
                get_bacnet_class_name(obj), obj_type_str, obj.objectIdentifier[1],
                obj.objectName, obj.description, 'lct', obj.presentValue,
                change_form,
            )

        return '<h4>Equipment: <u>{}</u> ID: {}</h4><table border="all">{}</table>'.format(eqp_type, eqp_id, rows)

    def _update_equipment_details(self, params: dict) -> str:
        """Port of updateEquipmentDetails()."""
        registry = self._registry
        eqp_type = params.get('Equipment_Type')
        eqp_id = params.get('Equipment_Id')

        if not registry or not eqp_type or eqp_type not in registry.get_all():
            return '<h4>UNABLE TO HANDLE THE PARAMETER CHANGE REQUEST</h4>'

        eqp_data = registry.get_equipment(eqp_type, eqp_id or '')
        if eqp_data is None:
            return '<h4>UNABLE TO HANDLE THE PARAMETER CHANGE REQUEST</h4>'

        param_name = params.get('description')
        if param_name and param_name in eqp_data:
            obj = eqp_data[param_name]
            new_val_raw = params.get('newValue')
            if new_val_raw is not None:
                new_val = self._coerce_value(new_val_raw, obj)
                if new_val is not None:
                    obj.presentValue = new_val
                    return '<h4>{}-{} Parameter {} Changed to <u>{}</u></h4>'.format(
                        eqp_type, eqp_id, param_name, new_val,
                    )

        return '<h4>UNABLE TO HANDLE THE PARAMETER CHANGE REQUEST</h4>'

    def _get_simulator_info(self, params: dict):
        """Return JSON describing this simulator: ddc_id, web_port, bacnet_address."""
        registry = self._registry
        info = {
            'ddc_id':          registry.site_ddc_id if registry else None,
            'web_port':        self._web_port,
            'bacnet_address':  self._my_address,
        }
        return ('json', json.dumps(info))

    def _get_plant_snapshot(self, params: dict):
        """Port of processPlantSnapshot()."""
        registry = self._registry
        if not registry:
            return ('json', '{}')

        snapshot: dict = {'Plant_Snapshot': {}}
        for eqp_type, instances in registry.get_all().items():
            if not instances:
                continue
            snapshot['Plant_Snapshot'][eqp_type] = {}
            for eqp_id, eqp_data in instances.items():
                eqp_label = eqp_data['OtherDetails']['EQUIPMENT_ID']
                entry = {
                    'BACnetDeviceAddress': self._my_address,
                    'Equipment_Numeric_Id': int(str(eqp_id), 16),
                    'Equipment_Group': '',
                    'Eqp_Attributes': {},
                    'Eqp_Metrics': {'Run_Hours': getRandomAnalogInput(2000, 4000, 0), 'Equipment_Faulty': False},
                }
                if 'ChildEqps' in eqp_data['OtherDetails']:
                    entry['EQP_COMPONENTS'] = {}
                    for ch_type, ch_ids in eqp_data['OtherDetails']['ChildEqps'].items():
                        entry['EQP_COMPONENTS'][ch_type] = self._child_snapshot(ch_type, sorted(ch_ids))

                for param_name, obj in eqp_data.items():
                    if param_name == 'OtherDetails':
                        continue
                    entry['Eqp_Attributes'][param_name] = {
                        'objId': '{}:{}'.format(obj.objectIdentifier[0], obj.objectIdentifier[1]),
                        'objName': obj.objectName,
                        'presentValue': obj.presentValue,
                    }
                snapshot['Plant_Snapshot'][eqp_type][eqp_label] = entry

        return ('json', json.dumps(snapshot))

    def _get_reader_file(self, params: dict, n_items: int = 14) -> str:
        """Port of processReaderFile()."""
        registry = self._registry
        if not registry:
            return ''

        ddc = self._my_address if registry.site_ddc_id is None else registry.site_ddc_id
        output = ''
        for instances in registry.get_all().values():
            for eqp_data in instances.values():
                batch, count = '', 0
                for param_name, obj in eqp_data.items():
                    if param_name == 'OtherDetails':
                        continue
                    count += 1
                    batch += ',{}:{},presentValue'.format(
                        obj.objectIdentifier[0], obj.objectIdentifier[1],
                    )
                    if count >= n_items:
                        output += '<p>{}{}'.format(ddc, batch)
                        batch, count = '', 0
                if count >= 1:
                    output += '<p>{}{}'.format(ddc, batch)
        return output

    def _reset_all_equipment(self, params: dict) -> str:
        """Port of processEquipmentResetRequest()."""
        registry = self._registry
        eqp_params = self._eqp_param_objects
        if not registry:
            return ''

        for eqp_type, instances in registry.get_all().items():
            for eqp_data in instances.values():
                for param_name, obj in eqp_data.items():
                    if param_name == 'OtherDetails':
                        continue
                    reset_val = getDeepObject(
                        eqp_params, [eqp_type, 'Equipment_Parameters', param_name, 'resetValue'],
                    )
                    if reset_val is not None:
                        obj.presentValue = reset_val
        return ''

    # ── helpers ────────────────────────────────────────────────────────────────

    def _coerce_value(self, raw_val: str, obj):
        """Port of checkPresentValue() — type-coerces value to match the object type."""
        if isinstance(obj, (WritableAnalogInputObject, WritableAnalogOutputObject, WritableAnalogValueObject)):
            try:
                return float(raw_val)
            except (ValueError, TypeError):
                return None
        if isinstance(obj, (WritableBinaryInputObject, WritableBinaryOutputObject, WritableBinaryValueObject)):
            upper = str(raw_val).upper()
            if upper in ('FALSE', 'INACTIVE'):
                return 'inactive'
            if upper in ('TRUE', 'ACTIVE'):
                return 'active'
            return None
        if isinstance(obj, WritableMultiStateValueObject):
            try:
                return int(raw_val)
            except (ValueError, TypeError):
                return None
        return None

    def _child_snapshot(self, ch_type: str, ch_ids: list) -> dict:
        """Port of prepareChildEquipmentSnapshot()."""
        registry = self._registry
        result = {}
        for ch_id in ch_ids:
            eqp_data = registry.get_equipment(ch_type, ch_id)
            if not eqp_data:
                continue
            eqp_label = eqp_data['OtherDetails']['EQUIPMENT_ID']
            entry = {
                'BACnetDeviceAddress': self._my_address,
                'Equipment_Numeric_Id': int(str(ch_id), 16),
                'Equipment_Group': '',
                'Eqp_Attributes': {},
                'Eqp_Metrics': {'Run_Hours': getRandomAnalogInput(2000, 4000, 0), 'Equipment_Faulty': False},
            }
            for param_name, obj in eqp_data.items():
                if param_name == 'OtherDetails':
                    continue
                entry['Eqp_Attributes'][param_name] = {
                    'objId': '{}:{}'.format(obj.objectIdentifier[0], obj.objectIdentifier[1]),
                    'objName': obj.objectName,
                    'presentValue': obj.presentValue,
                }
            result[eqp_label] = entry
        return result
