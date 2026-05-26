###############################################################
import json, csv, os
import threading
from datetime import datetime
try:
    from urlparse import urlparse, parse_qs
    from SocketServer import ThreadingMixIn, TCPServer
    from SimpleHTTPServer import SimpleHTTPRequestHandler
except ImportError:
    from urllib.parse import urlparse, parse_qs
    from socketserver import ThreadingMixIn, TCPServer
    from http.server import SimpleHTTPRequestHandler
###############################################################
# GLOBALS
_debug = 0
webDataCallback = None
###############################################################

# ── Vue.js dashboard HTML ─────────────────────────────────────────────────────
_VUE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BACnet Reader Dashboard</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; font-size: 13px; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  #app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

  /* ── Header ── */
  .hdr { background: #1a1f2e; border-bottom: 1px solid #2d3748; padding: 10px 18px; display: flex; align-items: center; gap: 14px; flex-shrink: 0; }
  .hdr-title { font-size: 15px; font-weight: 700; color: #63b3ed; letter-spacing: .3px; flex: 1; }
  .hdr-meta { font-size: 11px; color: #718096; }
  .btn { padding: 5px 12px; border-radius: 5px; border: 1px solid #4a5568; background: #2d3748; color: #e2e8f0; cursor: pointer; font-size: 12px; transition: background .15s; white-space: nowrap; }
  .btn:hover { background: #4a5568; }
  .btn.active { background: #2b6cb0; border-color: #3182ce; color: #fff; }
  .btn.danger { background: #742a2a; border-color: #c53030; }
  .spin { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Stats ── */
  .stats { display: flex; gap: 10px; padding: 10px 18px; background: #141824; border-bottom: 1px solid #2d3748; flex-shrink: 0; }
  .stat-card { flex: 1; background: #1a1f2e; border: 1px solid #2d3748; border-radius: 8px; padding: 10px 14px; text-align: center; }
  .stat-card .val { font-size: 24px; font-weight: 700; line-height: 1.1; }
  .stat-card .lbl { font-size: 10px; color: #718096; text-transform: uppercase; letter-spacing: .6px; margin-top: 2px; }
  .stat-blue .val  { color: #63b3ed; }
  .stat-green .val { color: #68d391; }
  .stat-red   .val { color: #fc8181; }
  .stat-amber .val { color: #f6ad55; }
  .stat-red.ok   .val { color: #68d391; }
  .stat-amber.ok .val { color: #68d391; }

  /* ── Filters ── */
  .filters { display: flex; align-items: center; gap: 10px; padding: 8px 18px; background: #1a1f2e; border-bottom: 1px solid #2d3748; flex-shrink: 0; flex-wrap: wrap; }
  .filters input, .filters select { background: #2d3748; border: 1px solid #4a5568; border-radius: 5px; color: #e2e8f0; padding: 5px 9px; font-size: 12px; outline: none; }
  .filters input { width: 220px; }
  .filters input:focus, .filters select:focus { border-color: #3182ce; }
  .filters select option { background: #2d3748; }
  .row-count { margin-left: auto; font-size: 11px; color: #718096; white-space: nowrap; }

  /* ── Table ── */
  .table-wrap { flex: 1; overflow: auto; padding: 0; }
  table { width: 100%; border-collapse: collapse; }
  thead th { position: sticky; top: 0; background: #1e2535; border-bottom: 2px solid #3182ce; padding: 7px 10px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #a0aec0; white-space: nowrap; cursor: pointer; user-select: none; }
  thead th:hover { background: #252d3d; color: #e2e8f0; }
  thead th .sort-icon { margin-left: 4px; opacity: .5; font-size: 10px; }
  thead th.sorted .sort-icon { opacity: 1; color: #63b3ed; }
  tbody tr { border-bottom: 1px solid #1e2535; transition: background .1s; }
  tbody tr:hover { background: #1e2535; }
  tbody tr.row-error { background: rgba(197,48,48,.1); }
  tbody tr.row-error:hover { background: rgba(197,48,48,.18); }
  tbody td { padding: 5px 10px; color: #cbd5e0; vertical-align: middle; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  tbody td.val-cell { font-family: monospace; font-size: 12px; color: #68d391; }
  tbody td.val-cell.no-val { color: #fc8181; }
  .badge { display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 10px; font-weight: 600; }
  .badge-ok  { background: rgba(72,187,120,.15); color: #68d391; border: 1px solid rgba(72,187,120,.3); }
  .badge-err { background: rgba(245,101,101,.15); color: #fc8181; border: 1px solid rgba(245,101,101,.3); }
  .badge-nd  { background: rgba(160,174,192,.1);  color: #718096;  border: 1px solid rgba(160,174,192,.2); }
  .empty-row td { text-align: center; padding: 40px; color: #4a5568; font-style: italic; }
</style>
</head>
<body>
<div id="app">

  <!-- Header -->
  <div class="hdr">
    <span class="hdr-title">&#9632; BACnet Reader &mdash; Live Dashboard</span>
    <span class="hdr-meta" v-if="lastUpdate">Last update: {{ lastUpdate }}</span>
    <span class="hdr-meta" v-if="loading"><span class="spin">&#8635;</span> Loading&hellip;</span>
    <button class="btn" @click="fetchData" :disabled="loading">&#8635; Refresh</button>
    <button class="btn" :class="{ active: autoRefresh }" @click="toggleRefresh">
      Auto {{ autoRefresh ? 'ON' : 'OFF' }}
    </button>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat-card stat-blue">
      <div class="val">{{ stats.ddcCount }}</div>
      <div class="lbl">DDC Count</div>
    </div>
    <div class="stat-card stat-green">
      <div class="val">{{ stats.totalPoints }}</div>
      <div class="lbl">Total Points</div>
    </div>
    <div class="stat-card stat-red" :class="{ ok: stats.errorDDC === 0 }">
      <div class="val">{{ stats.errorDDC }}</div>
      <div class="lbl">Error DDCs</div>
    </div>
    <div class="stat-card stat-amber" :class="{ ok: stats.errorPoints === 0 }">
      <div class="val">{{ stats.errorPoints }}</div>
      <div class="lbl">Error Points</div>
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
      <option value="ok">OK only</option>
      <option value="error">Error only</option>
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
            <span v-else-if="rows.length === 0">No data received from BACnet reader. Ensure bacnet_reader.py is running.</span>
            <span v-else>No rows match the current filters.</span>
          </td>
        </tr>
        <tr v-for="(row, idx) in filtered" :key="idx"
            :class="{ 'row-error': isError(row) }">
          <td :title="row.timestamp">{{ row.timestamp }}</td>
          <td :title="row.gl_code"><strong>{{ row.gl_code }}</strong></td>
          <td :title="row.ddc_id">{{ row.ddc_id }}</td>
          <td>{{ row.object_name }}</td>
          <td>{{ row.object_id }}</td>
          <td>{{ row.p_name }}</td>
          <td :title="row.display_name">{{ row.display_name }}</td>
          <td class="val-cell" :class="{ 'no-val': isError(row) }">
            {{ isError(row) ? '—' : row.present_value }}
          </td>
          <td>
            <span v-if="row.db_inserted === 'True'"  class="badge badge-ok">OK</span>
            <span v-else-if="row.db_inserted === 'False'" class="badge badge-err">No</span>
            <span v-else class="badge badge-nd">{{ row.db_inserted || '—' }}</span>
          </td>
          <td class="val-cell">{{ row.db_inserted_value || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>

</div>
<script>
const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

const COLS = [
  { key: 'timestamp',         label: 'Timestamp' },
  { key: 'gl_code',           label: 'GL Code' },
  { key: 'ddc_id',            label: 'DDC / Address' },
  { key: 'object_name',       label: 'Object Type' },
  { key: 'object_id',         label: 'Instance' },
  { key: 'p_name',            label: 'P-Name' },
  { key: 'display_name',      label: 'Display Name' },
  { key: 'present_value',     label: 'Value' },
  { key: 'db_inserted',       label: 'DB Write' },
  { key: 'db_inserted_value', label: 'DB Value' },
];

const ERROR_VALUES = new Set(['', 'None', 'none', 'null', 'NULL', 'N/A', 'n/a', 'undefined']);

createApp({
  setup() {
    const rows        = ref([]);
    const loading     = ref(false);
    const lastUpdate  = ref('');
    const autoRefresh = ref(true);
    const searchText  = ref('');
    const ddcFilter   = ref('');
    const statusFilter= ref('all');
    const sortKey     = ref('ddc_id');
    const sortDir     = ref(1);
    let   timer       = null;

    /* ── helpers ─────────────────────────────────────────── */
    const isError = row => {
      const pv = row.present_value;
      return pv === null || pv === undefined || ERROR_VALUES.has(String(pv).trim());
    };

    /* ── computed ────────────────────────────────────────── */
    const stats = computed(() => {
      const allDDCs   = new Set(rows.value.map(r => r.ddc_id));
      const errRows   = rows.value.filter(isError);
      const errDDCs   = new Set(errRows.map(r => r.ddc_id));
      return {
        ddcCount:    allDDCs.size,
        totalPoints: rows.value.length,
        errorDDC:    errDDCs.size,
        errorPoints: errRows.length,
      };
    });

    const uniqueDDCs = computed(() =>
      [...new Set(rows.value.map(r => r.ddc_id))].sort()
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

      if (statusFilter.value === 'ok') {
        data = data.filter(r => !isError(r));
      } else if (statusFilter.value === 'error') {
        data = data.filter(r => isError(r));
      }

      const k   = sortKey.value;
      const dir = sortDir.value;
      return [...data].sort((a, b) =>
        String(a[k] ?? '').localeCompare(String(b[k] ?? ''), undefined, { numeric: true }) * dir
      );
    });

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

    const startTimer = () => {
      if (timer) clearInterval(timer);
      if (autoRefresh.value) timer = setInterval(fetchData, 5000);
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
      isError, setSort, sortIcon, fetchData, toggleRefresh,
    };
  }
}).mount('#app');
</script>
</body>
</html>"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class GLHttpRequestHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/data':
            self._serve_data_json()
        else:
            self._serve_vue_html()

    # ── /data — JSON snapshot ─────────────────────────────────────────────

    def _serve_data_json(self):
        global webDataCallback
        data = []
        if webDataCallback is not None:
            try:
                for row in webDataCallback():
                    data.append({
                        'timestamp':         str(row[0]) if len(row) > 0 and row[0] is not None else '',
                        'gl_code':           str(row[1]) if len(row) > 1 and row[1] is not None else '',
                        'ddc_id':            str(row[2]) if len(row) > 2 and row[2] is not None else '',
                        'object_name':       str(row[3]) if len(row) > 3 and row[3] is not None else '',
                        'object_id':         str(row[4]) if len(row) > 4 and row[4] is not None else '',
                        'p_name':            str(row[5]) if len(row) > 5 and row[5] is not None else '',
                        'display_name':      str(row[6]) if len(row) > 6 and row[6] is not None else '',
                        'present_value':     str(row[7]) if len(row) > 7 and row[7] is not None else '',
                        'db_inserted':       str(row[8]) if len(row) > 8 and row[8] is not None else '',
                        'db_inserted_value': str(row[9]) if len(row) > 9 and row[9] is not None else '',
                    })
            except Exception as e:
                print('GLHttpRequestHandler._serve_data_json error: {}'.format(e))

        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    # ── / — Vue.js dashboard ──────────────────────────────────────────────

    def _serve_vue_html(self):
        body = _VUE_HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── legacy compat ─────────────────────────────────────────────────────

    def processMyData(self):
        """Kept for backward compatibility; returns the Vue.js HTML."""
        return _VUE_HTML

    def log_message(self, fmt, *args):
        pass  # suppress per-request console noise


class GLThreadedTCPServer(ThreadingMixIn, TCPServer):
    pass


###############################################################
# INITIALIZATION
def initializeWebServer(myWebPort=7060, mycallback=None):
    global webDataCallback
    if mycallback is not None:
        webDataCallback = mycallback
    args = None
    try:
        appHttpServer = GLThreadedTCPServer(('0.0.0.0', myWebPort), GLHttpRequestHandler)
        print("    - server: {}".format(appHttpServer))
        appServerThreadGenerator = threading.Thread(target=appHttpServer.serve_forever)
        print("    - server_thread: {}".format(appServerThreadGenerator))
        appServerThreadGenerator.daemon = True
        appServerThreadGenerator.start()
        print('GL_{}: Server Started at : {}'.format('Server', myWebPort))
    except Exception as err:
        print('initializeWebServer - GL_{}:Initialization Error: {}'.format(10000, err))
    finally:
        return args


def main():
    try:
        initializeWebServer()
    except Exception as e:
        print("an error has occurred: %s", e)
    finally:
        print("finally")


if __name__ == "__main__":
    pass  # main()
