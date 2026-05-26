"""
request_handler — HTTP server components for the BACnet gateway.

SRP: Only responsible for receiving HTTP requests, building response bytes,
     and (optionally) enqueuing parsed requests.

DIP: The RequestQueue is injected as a class variable before the server
     starts (standard Python HTTP-server pattern — TCPServer creates handler
     instances without arguments).

Extracted from GLHttpRequestHandler and GLThreadedTCPServer in
bacnet_writer.py.  The LMS helper functions are kept here but isolated
in private methods.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import threading
from typing import TYPE_CHECKING, Optional

try:
    from socketserver import ThreadingMixIn, TCPServer
    from http.server import SimpleHTTPRequestHandler
    from urllib.parse import urlparse
except ImportError:
    from SocketServer import ThreadingMixIn, TCPServer          # type: ignore
    from SimpleHTTPServer import SimpleHTTPRequestHandler       # type: ignore
    from urlparse import urlparse                               # type: ignore

import requests

from gateway.request_parser import parse_http_request

if TYPE_CHECKING:
    from core.request_queue import RequestQueue

logger = logging.getLogger(__name__)


# ── Vue.js dashboard HTML ──────────────────────────────────────────────────────

_VUE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BACnet Writer Dashboard</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; font-size: 13px; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  #app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

  /* ── Header ── */
  .hdr { background: #1a1f2e; border-bottom: 1px solid #2d3748; padding: 10px 18px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
  .hdr-title { font-size: 15px; font-weight: 700; color: #9f7aea; letter-spacing: .3px; flex: 1; }
  .hdr-meta { font-size: 11px; color: #718096; }
  .btn { padding: 5px 12px; border-radius: 5px; border: 1px solid #4a5568; background: #2d3748; color: #e2e8f0; cursor: pointer; font-size: 12px; transition: background .15s; white-space: nowrap; }
  .btn:hover { background: #4a5568; }
  .btn.active { background: #553c9a; border-color: #9f7aea; color: #fff; }
  .btn.danger { background: #742a2a; border-color: #c53030; color: #fff; }
  .btn.danger:hover { background: #9b2c2c; }
  .spin { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Stats ── */
  .stats { display: flex; gap: 10px; padding: 10px 18px; background: #141824; border-bottom: 1px solid #2d3748; flex-shrink: 0; }
  .stat-card { flex: 1; background: #1a1f2e; border: 1px solid #2d3748; border-radius: 8px; padding: 10px 14px; text-align: center; }
  .stat-card .val { font-size: 24px; font-weight: 700; line-height: 1.1; }
  .stat-card .lbl { font-size: 10px; color: #718096; text-transform: uppercase; letter-spacing: .6px; margin-top: 2px; }
  .stat-blue   .val { color: #63b3ed; }
  .stat-green  .val { color: #68d391; }
  .stat-red    .val { color: #fc8181; }
  .stat-amber  .val { color: #f6ad55; }
  .stat-purple .val { color: #b794f4; }
  .stat-red.ok   .val { color: #68d391; }
  .stat-amber.ok .val { color: #68d391; }

  /* ── Filters ── */
  .filters { display: flex; align-items: center; gap: 10px; padding: 8px 18px; background: #1a1f2e; border-bottom: 1px solid #2d3748; flex-shrink: 0; flex-wrap: wrap; }
  .filters input, .filters select { background: #2d3748; border: 1px solid #4a5568; border-radius: 5px; color: #e2e8f0; padding: 5px 9px; font-size: 12px; outline: none; }
  .filters input { width: 220px; }
  .filters input:focus, .filters select:focus { border-color: #9f7aea; }
  .filters select option { background: #2d3748; }
  .row-count { margin-left: auto; font-size: 11px; color: #718096; white-space: nowrap; }

  /* ── Table ── */
  .table-wrap { flex: 1; overflow: auto; }
  table { width: 100%; border-collapse: collapse; }
  thead th { position: sticky; top: 0; background: #1e2535; border-bottom: 2px solid #553c9a; padding: 7px 10px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #a0aec0; white-space: nowrap; cursor: pointer; user-select: none; }
  thead th:hover { background: #252d3d; color: #e2e8f0; }
  thead th .sort-icon { margin-left: 4px; opacity: .5; font-size: 10px; }
  thead th.sorted .sort-icon { opacity: 1; color: #b794f4; }
  tbody tr { border-bottom: 1px solid #1e2535; transition: background .1s; }
  tbody tr:hover { background: #1e2535; }
  tbody tr.row-pending { background: rgba(246,173,85,.07); }
  tbody tr.row-pending:hover { background: rgba(246,173,85,.13); }
  tbody tr.row-failed  { background: rgba(197,48,48,.1); }
  tbody tr.row-failed:hover  { background: rgba(197,48,48,.17); }
  tbody tr.row-success { background: rgba(72,187,120,.06); }
  tbody tr.row-success:hover { background: rgba(72,187,120,.12); }
  tbody td { padding: 5px 10px; color: #cbd5e0; vertical-align: middle; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  tbody td.val-cell { font-family: monospace; font-size: 12px; color: #b794f4; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; }
  .badge-pending { background: rgba(246,173,85,.15); color: #f6ad55; border: 1px solid rgba(246,173,85,.3); }
  .badge-success { background: rgba(72,187,120,.15); color: #68d391; border: 1px solid rgba(72,187,120,.3); }
  .badge-failed  { background: rgba(245,101,101,.15); color: #fc8181; border: 1px solid rgba(245,101,101,.3); }
  .badge-other   { background: rgba(160,174,192,.1);  color: #a0aec0; border: 1px solid rgba(160,174,192,.2); }
  .empty-row td { text-align: center; padding: 40px; color: #4a5568; font-style: italic; }
</style>
</head>
<body>
<div id="app">

  <!-- Header -->
  <div class="hdr">
    <span class="hdr-title">&#9654; BACnet Writer &mdash; Command Dashboard</span>
    <span class="hdr-meta" v-if="lastUpdate">Last update: {{ lastUpdate }}</span>
    <span class="hdr-meta" v-if="loading"><span class="spin">&#8635;</span> Loading&hellip;</span>
    <button class="btn" @click="fetchData" :disabled="loading">&#8635; Refresh</button>
    <button class="btn" :class="{ active: autoRefresh }" @click="toggleRefresh">
      Auto {{ autoRefresh ? 'ON' : 'OFF' }}
    </button>
    <button class="btn danger" @click="clearLog" title="Clear all logged commands">&#128465; Clear Log</button>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat-card stat-blue">
      <div class="val">{{ stats.total }}</div>
      <div class="lbl">Commands Received</div>
    </div>
    <div class="stat-card stat-amber" :class="{ ok: stats.pending === 0 }">
      <div class="val">{{ stats.pending }}</div>
      <div class="lbl">Pending</div>
    </div>
    <div class="stat-card stat-green">
      <div class="val">{{ stats.success }}</div>
      <div class="lbl">Success</div>
    </div>
    <div class="stat-card stat-red" :class="{ ok: stats.failed === 0 }">
      <div class="val">{{ stats.failed }}</div>
      <div class="lbl">Failed</div>
    </div>
    <div class="stat-card stat-purple">
      <div class="val">{{ stats.ddcCount }}</div>
      <div class="lbl">DDCs Targeted</div>
    </div>
  </div>

  <!-- Filters -->
  <div class="filters">
    <input v-model="searchText" placeholder="&#128269; Search any column&hellip;" />
    <select v-model="ddcFilter">
      <option value="">All DDCs</option>
      <option v-for="d in uniqueDDCs" :key="d" :value="d">{{ d }}</option>
    </select>
    <select v-model="statusFilter">
      <option value="all">All Status</option>
      <option value="pending">Pending</option>
      <option value="success">Success</option>
      <option value="failed">Failed</option>
    </select>
    <span class="row-count">Showing {{ filtered.length }} / {{ rows.length }} rows</span>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th v-for="col in COLS" :key="col.key"
              :class="{ sorted: sortKey === col.key }"
              @click="setSort(col.key)">
            {{ col.label }}
            <span class="sort-icon">{{ sortIcon(col.key) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="filtered.length === 0">
          <td :colspan="COLS.length">
            <span v-if="loading">Loading data&hellip;</span>
            <span v-else-if="rows.length === 0">No write commands received yet. Commands appear here when clients POST to the writer.</span>
            <span v-else>No rows match the current filters.</span>
          </td>
        </tr>
        <tr v-for="(row, idx) in filtered" :key="idx"
            :class="rowClass(row)">
          <td :title="row.timestamp">{{ row.timestamp }}</td>
          <td :title="row.gl_code"><strong>{{ row.gl_code || '—' }}</strong></td>
          <td :title="row.ddc_id">{{ row.ddc_id }}</td>
          <td>{{ row.object_name }}</td>
          <td>{{ row.object_id }}</td>
          <td>{{ row.p_name || '—' }}</td>
          <td :title="row.display_name">{{ row.display_name || '—' }}</td>
          <td class="val-cell">{{ row.value }}</td>
          <td :title="row.command_success">
            <span :class="statusBadgeClass(row.command_success)">
              {{ statusLabel(row.command_success) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

</div>
<script>
const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

const COLS = [
  { key: 'timestamp',       label: 'Timestamp' },
  { key: 'gl_code',         label: 'GL Code' },
  { key: 'ddc_id',          label: 'DDC / Address' },
  { key: 'object_name',     label: 'Object Type' },
  { key: 'object_id',       label: 'Instance' },
  { key: 'p_name',          label: 'P-Name' },
  { key: 'display_name',    label: 'Display Name' },
  { key: 'value',           label: 'Write Value' },
  { key: 'command_success', label: 'Status' },
];

const statusOf = s => {
  if (!s) return 'other';
  const low = String(s).toLowerCase().trim();
  if (low === 'pending') return 'pending';
  // BACnet ACK values from application.py
  if (low === 'acknowledged' || low === 'success' || low === 'true' || low === '1' || low === 'ok') return 'success';
  if (low === 'not-acknowledged' || low === 'failed' || low === 'false' || low === '0'
      || low.startsWith('error') || low === 'unknown') return 'failed';
  return 'other';
};

createApp({
  setup() {
    const rows        = ref([]);
    const loading     = ref(false);
    const lastUpdate  = ref('');
    const autoRefresh = ref(true);
    const searchText  = ref('');
    const ddcFilter   = ref('');
    const statusFilter= ref('all');
    const sortKey     = ref('timestamp');
    const sortDir     = ref(-1);   // newest first
    let   timer       = null;

    /* ── computed ────────────────────────────────────────── */
    const stats = computed(() => {
      const total   = rows.value.length;
      const pending = rows.value.filter(r => statusOf(r.command_success) === 'pending').length;
      const success = rows.value.filter(r => statusOf(r.command_success) === 'success').length;
      const failed  = rows.value.filter(r => statusOf(r.command_success) === 'failed').length;
      const ddcCount = new Set(rows.value.map(r => r.ddc_id).filter(Boolean)).size;
      return { total, pending, success, failed, ddcCount };
    });

    const uniqueDDCs = computed(() =>
      [...new Set(rows.value.map(r => r.ddc_id).filter(Boolean))].sort()
    );

    const filtered = computed(() => {
      let data = rows.value;

      const q = searchText.value.trim().toLowerCase();
      if (q) {
        data = data.filter(r =>
          Object.values(r).some(v => String(v ?? '').toLowerCase().includes(q))
        );
      }

      if (ddcFilter.value) {
        data = data.filter(r => r.ddc_id === ddcFilter.value);
      }

      if (statusFilter.value !== 'all') {
        data = data.filter(r => statusOf(r.command_success) === statusFilter.value);
      }

      const k   = sortKey.value;
      const dir = sortDir.value;
      return [...data].sort((a, b) =>
        String(a[k] ?? '').localeCompare(String(b[k] ?? ''), undefined, { numeric: true }) * dir
      );
    });

    /* ── helpers ─────────────────────────────────────────── */
    const rowClass = row => ({
      'row-pending': statusOf(row.command_success) === 'pending',
      'row-success': statusOf(row.command_success) === 'success',
      'row-failed':  statusOf(row.command_success) === 'failed',
    });

    const statusBadgeClass = s => {
      const st = statusOf(s);
      return {
        badge: true,
        'badge-pending': st === 'pending',
        'badge-success': st === 'success',
        'badge-failed':  st === 'failed',
        'badge-other':   st === 'other',
      };
    };

    // Short label for badge; full value shown in tooltip (title attribute)
    const STATUS_LABELS = {
      pending: 'Pending',
      success: 'ACK',
      failed:  'Failed',
      other:   'Unknown',
    };
    const statusLabel = s => {
      const st = statusOf(s);
      // For errors, show trimmed error text (first 20 chars)
      if (st === 'failed' && String(s).toLowerCase().startsWith('error')) {
        return String(s).slice(0, 22) + (s.length > 22 ? '\\u2026' : '');
      }
      return STATUS_LABELS[st] || s;
    };

    /* ── sort ────────────────────────────────────────────── */
    const setSort = key => {
      if (sortKey.value === key) {
        sortDir.value = -sortDir.value;
      } else {
        sortKey.value = key;
        sortDir.value = 1;
      }
    };

    const sortIcon = key => {
      if (sortKey.value !== key) return '\\u21d5';
      return sortDir.value === 1 ? '\\u2191' : '\\u2193';
    };

    /* ── data fetch ──────────────────────────────────────── */
    const fetchData = async () => {
      loading.value = true;
      try {
        const resp = await fetch('/data');
        if (resp.ok) {
          rows.value   = await resp.json();
          lastUpdate.value = new Date().toLocaleTimeString();
        }
      } catch (e) {
        console.error('fetch /data error:', e);
      } finally {
        loading.value = false;
      }
    };

    const clearLog = async () => {
      try {
        await fetch('/clear', { method: 'POST' });
        rows.value = [];
      } catch (e) {
        console.error('clear error:', e);
      }
    };

    const startTimer = () => {
      if (timer) clearInterval(timer);
      if (autoRefresh.value) timer = setInterval(fetchData, 3000);
    };

    const toggleRefresh = () => {
      autoRefresh.value = !autoRefresh.value;
      startTimer();
    };

    onMounted(() => { fetchData(); startTimer(); });
    onUnmounted(() => { if (timer) clearInterval(timer); });

    return {
      COLS, rows, loading, lastUpdate, autoRefresh,
      searchText, ddcFilter, statusFilter,
      sortKey, sortDir,
      stats, uniqueDDCs, filtered,
      rowClass, statusBadgeClass, statusLabel, setSort, sortIcon,
      fetchData, clearLog, toggleRefresh,
    };
  }
}).mount('#app');
</script>
</body>
</html>"""


# ── threaded TCP server ────────────────────────────────────────────────────────

class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    """
    TCPServer that spawns a new thread for each incoming connection.
    Direct port of GLThreadedTCPServer.
    """
    allow_reuse_address = True


# ── HTTP handler ───────────────────────────────────────────────────────────────

class HttpRequestHandler(SimpleHTTPRequestHandler):
    """
    Handles GET and POST HTTP requests for the BACnet gateway.

    Class variables are set before the server starts:
        request_queue : RequestQueue  — the application-level request queue
        config        : ServerConfig  — server configuration
    """

    # Injected via configure() before the server is created
    request_queue: Optional['RequestQueue'] = None
    config = None

    # In-memory log of BACnet write commands (shown on bare GET '/')
    bacnet_requests: list = []

    # CSV lookup: (ddc_id, obj_type, obj_id) -> {'p_name': ..., 'display_name': ...}
    _name_lookup: dict = {}

    # Reverse controller map: BACnet address → logical DDC name (e.g. '31:26' → 'DDC01_02')
    _address_to_ddc: dict = {}

    _CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'eqp_name_handling.csv')

    # ── class-level setup ─────────────────────────────────────────────────────

    @classmethod
    def configure(cls, request_queue: 'RequestQueue', config, controller_map_json: str = '') -> None:
        """Wire dependencies before the server is started."""
        cls.request_queue = request_queue
        cls.config = config
        cls._load_name_lookup()
        if controller_map_json:
            try:
                fwd = json.loads(controller_map_json)
                # Build a unified address→DDC map that handles both formats:
                #   "DDC01": "192.168.1.106:2001"  → reverse: IP:port → DDC name
                #   "23688:4": "DDC01"             → direct:  BACnet addr → DDC name
                # A key that contains ':' is treated as an address (BACnet network:node
                # or IP:port); a key without ':' is treated as a DDC name.
                addr_to_ddc = {}
                ddc_to_addrs = {}   # DDC name → list of all its known addresses
                for k, v in fwd.items():
                    if ':' in k:
                        # key is a BACnet address, value is the DDC name
                        addr_to_ddc[k] = v
                        ddc_to_addrs.setdefault(v, []).append(k)
                    else:
                        # key is a DDC name, value is the BACnet/IP address
                        addr_to_ddc[v] = k
                        ddc_to_addrs.setdefault(k, []).append(v)
                cls._address_to_ddc = addr_to_ddc

                # Duplicate _name_lookup entries for every known address of each DDC
                # so lookups succeed regardless of the address format in the URL.
                extra = {}
                for (ddc_name, obj_type, obj_id), data in list(cls._name_lookup.items()):
                    for addr in ddc_to_addrs.get(ddc_name, []):
                        extra[(addr, obj_type, obj_id)] = data
                cls._name_lookup.update(extra)
                logger.info(
                    '_name_lookup entries: %d (after address indexing for %d DDCs)',
                    len(cls._name_lookup), len(ddc_to_addrs),
                )
            except Exception as exc:
                logger.warning('Could not parse controllermap: %s', exc)

    @classmethod
    def _load_name_lookup(cls) -> None:
        """Load eqp_name_handling.csv into _name_lookup for fast display enrichment."""
        try:
            with open(cls._CSV_PATH, newline='') as f:
                for row in csv.DictReader(f):
                    ddc  = row['ddc_id'].strip()
                    otype = row['obj_type'].strip()
                    oid   = str(row['obj_id']).strip()
                    cls._name_lookup[(ddc, otype, oid)] = {
                        'p_name':       row.get('gl_param_name', '').strip(),
                        'display_name': row.get('display_name', '').strip(),
                        'gl_code':      row.get('gl_code', '').strip(),
                    }
            logger.info('_name_lookup loaded: %d entries from %s', len(cls._name_lookup), cls._CSV_PATH)
        except Exception as exc:
            logger.warning('Could not load name lookup CSV (%s): %s', cls._CSV_PATH, exc)

    # BACnet object type number → name (ASHRAE 135 Table 23-2)
    _BACNET_OBJ_TYPES = {
        '0': 'analogInput', '1': 'analogOutput', '2': 'analogValue',
        '3': 'binaryInput', '4': 'binaryOutput', '5': 'binaryValue',
        '6': 'calendar', '7': 'command', '8': 'device', '9': 'eventEnrollment',
        '10': 'file', '11': 'group', '12': 'loop', '13': 'multiStateInput',
        '14': 'multiStateOutput', '15': 'notificationClass', '16': 'program',
        '17': 'schedule', '18': 'averaging', '19': 'multiStateValue',
        '20': 'trendLog', '21': 'lifeSafetyPoint', '22': 'lifeSafetyZone',
        '23': 'accumulator', '24': 'pulseConverter',
    }

    @classmethod
    def _build_display_entry(cls, result: dict) -> dict:
        """
        Extract the 6 display fields from a parsed request dict.
        object_name = BACnet object type string (e.g. 'binaryOutput')
        object_id   = numeric instance (e.g. '1')
        ddc_id      = destination address / controller alias
        p_name      = gl_param_name from CSV (falls back to URL property)
        display_name= human-readable name from CSV
        command_success = 'Pending' until updated
        """
        parts = result.get('request_parts', [])
        raw_addr   = (parts[2] if len(parts) > 2 else '').strip()
        raw_obj    = (parts[3] if len(parts) > 3 else '').strip()
        p_name_url = (parts[4] if len(parts) > 4 else '').strip()

        # resolve BACnet address → logical DDC name (e.g. '192.168.1.106:2001' → 'DDC01')
        ddc_id = cls._address_to_ddc.get(raw_addr, raw_addr)

        raw_type, _, obj_id = raw_obj.partition(':')
        raw_type = raw_type.strip()
        obj_id   = obj_id.strip()
        # resolve numeric type code → name (fall back to raw string if already named)
        obj_type = cls._BACNET_OBJ_TYPES.get(raw_type, raw_type)

        # Primary lookup: by resolved DDC name; fallback: by raw IP:port address
        lookup = (
            cls._name_lookup.get((ddc_id, obj_type, obj_id))
            or cls._name_lookup.get((raw_addr, obj_type, obj_id))
            or {}
        )
        logger.debug('_build_display_entry: addr=%s ddc=%s type=%s id=%s lookup=%s',
                     raw_addr, ddc_id, obj_type, obj_id, bool(lookup))

        return {
            'timestamp': result.get('Request_At', ''),
            'gl_code': lookup.get('gl_code', ''),
            'ddc_id': ddc_id,
            'object_name': obj_type,
            'object_id': obj_id,
            'p_name': lookup.get('p_name') or p_name_url,
            'display_name': lookup.get('display_name', ''),
            'value': parts[5] if len(parts) > 5 else '',
            'command_success': 'Pending',
        }

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path).path

        # ── /data — JSON snapshot of command log ──────────────────────────
        if parsed_path == '/data':
            self._serve_data_json()
            return

        cur_thread = threading.current_thread()
        logger.debug('do_GET — thread: %r', cur_thread)

        result = parse_http_request(self.client_address, self.requestline, self.path)

        # Enqueue if path has enough parts (service / address / ...)
        if len(result['request_parts']) > 2 and self.request_queue is not None:
            req_path = '/'.join(result['request_parts'])
            existing = next(
                (e for e in self.bacnet_requests
                 if e.get('_req_path') == req_path and e.get('command_success') == 'Pending'),
                None,
            )
            if existing is None:
                entry = self._build_display_entry(result)
                entry['request_uuid'] = result.get('request_uuid')
                entry['_req_path'] = req_path
                self.bacnet_requests.append(entry)
                result['_status_callback'] = lambda s, _e=entry: _e.update({'command_success': s})
                self.request_queue.push(result)
            else:
                logger.debug('do_GET — duplicate pending request, skipping: %s', req_path)
            content_type = 'text/plain'
            body_bytes = json.dumps({k: v for k, v in result.items() if not k.startswith('_')}).encode('utf-8')
        else:
            # bare '/' or unknown path — serve the Vue.js dashboard
            content_type = 'text/html; charset=utf-8'
            body_bytes = _VUE_HTML.encode('utf-8')

        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path

        # ── /clear — reset command log ────────────────────────────────────
        if parsed_path == '/clear':
            HttpRequestHandler.bacnet_requests.clear()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"cleared": true}')
            return

        logger.info(
            'do_POST — client: %s request: %s',
            ':'.join(map(str, self.client_address)),
            self.requestline,
        )
        content_length = int(self.headers.get('Content-Length', 0))
        raw_data = self.rfile.read(content_length)
        post_json = json.loads(raw_data)
        logger.info('do_POST — body: %s', post_json)

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        lms_keys = [
            'WLMSGroupControl', 'wacGroupControl', 'wacChannelSelection',
            'analogCtrlChannelControl', 'analogCtrldeviceTypeSelection', 'daliGroupControl',
        ]
        if any(k in self.requestline for k in lms_keys):
            result = self._process_lms_request(post_json)
        else:
            result = parse_http_request(
                self.client_address, self.requestline, self.path, post_json
            )
            if len(result['request_parts']) > 2 and self.request_queue is not None:
                self.request_queue.push(result)

        self.wfile.write(json.dumps(result).encode('utf-8'))

    # ── private helpers ───────────────────────────────────────────────────────

    _DISPLAY_COLUMNS = ['timestamp', 'gl_code', 'ddc_id', 'object_name', 'object_id', 'p_name', 'display_name', 'value', 'command_success']

    def _serve_data_json(self) -> None:
        """Return the in-memory command log as a JSON array."""
        safe_entries = [
            {k: str(v) if v is not None else '' for k, v in entry.items() if not k.startswith('_')}
            for entry in HttpRequestHandler.bacnet_requests
        ]
        body = json.dumps(safe_entries).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _render_request_table(requests_log: list) -> str:
        """Legacy: kept for compatibility. Returns the Vue.js HTML."""
        return _VUE_HTML

    @staticmethod
    def _process_lms_request(data: dict) -> dict:
        """Fire-and-forget POST to LMS command-status endpoints."""
        url_fmt = 'https://localhost/v1/lights/{}/commandstatus'
        body = {'status': 'success'}
        urls = []
        if 'DALI' in data:
            urls += [url_fmt.format(d['cmd']) for d in data['DALI'].get('dali', [])]
        if 'WAC' in data:
            urls += [url_fmt.format(w['cmd']) for w in data['WAC'].get('wac', [])]
        for url in urls:
            try:
                requests.post(url=url, json=body, verify=False, timeout=2)
            except Exception as exc:
                logger.error('_process_lms_request error %s: %s', url, exc)
        return {'data': {'returnCode': 0}}

    def log_message(self, fmt, *args):
        pass  # suppress per-request console noise
