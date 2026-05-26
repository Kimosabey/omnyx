"""
kafka_bacnet_bridge.py — HTTP bridge for Real Stack Stress Test.

Receives JSON telemetry POSTs from bacnet_reader.py, publishes each
payload to Kafka (pbs.telemetry.real) and writes a record to MySQL
(gl_pbs_stress_test). Logs metrics every 10 seconds and generates
Stress_Test_Report_04_RealStack.md on exit.

Usage
-----
  python kafka_bacnet_bridge.py
      Defaults: HTTP=127.0.0.1:8899  Kafka=localhost:9092  MySQL=localhost:3306

  python kafka_bacnet_bridge.py --http-port 8899 --kafka localhost:9092
"""
import argparse
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import mysql.connector
import psutil
from confluent_kafka import Producer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KAFKA_TOPIC   = 'pbs.telemetry.real'
REPORT_FILE   = 'docs/testing/reports/Stress_Test_Report_04_RealStack.md'
STATS_INTERVAL = 10   # seconds between metric prints

# ---------------------------------------------------------------------------
# Shared state (thread-safe via lock)
# ---------------------------------------------------------------------------
_lock          = threading.Lock()
_total_rx      = 0       # total HTTP posts received
_total_kafka   = 0       # total messages published to Kafka
_total_db      = 0       # total rows inserted to MySQL
_db_latency_ms = []      # per-insert latency samples
_timeline      = []      # list of stat snapshots for report
_start_time    = None

# ---------------------------------------------------------------------------
# Kafka producer (global, thread-safe with poll)
# ---------------------------------------------------------------------------
_producer: Producer = None

def _make_producer(bootstrap: str) -> Producer:
    return Producer({
        'bootstrap.servers': bootstrap,
        'client.id': 'bacnet-bridge',
        'compression.type': 'lz4',
        'linger.ms': 5,
    })

# ---------------------------------------------------------------------------
# MySQL connection pool (one connection per thread via thread-local)
# ---------------------------------------------------------------------------
_db_config = {}
_tls = threading.local()

def _get_db():
    if not hasattr(_tls, 'conn') or not _tls.conn.is_connected():
        _tls.conn = mysql.connector.connect(**_db_config)
        _tls.cursor = _tls.conn.cursor()
        _tls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_log (
                id            BIGINT AUTO_INCREMENT PRIMARY KEY,
                received_at   DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                ddc_id        VARCHAR(64),
                measured_time VARCHAR(64),
                payload_json  MEDIUMTEXT
            )
        """)
        _tls.conn.commit()
    return _tls.conn, _tls.cursor

# ---------------------------------------------------------------------------
# Kafka container CPU helper (background thread)
# ---------------------------------------------------------------------------
_kafka_cpu = 0.0
_mysql_cpu = 0.0
_container_polling = True

def _poll_container_stats():
    global _kafka_cpu, _mysql_cpu
    while _container_polling:
        try:
            r = subprocess.run(
                ['docker', 'stats', 'gl-test-kafka', 'gl-mysql-test',
                 '--no-stream', '--format', '{{.Name}},{{.CPUPerc}}'],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.strip().splitlines():
                parts = line.split(',')
                if len(parts) == 2:
                    name, cpu_str = parts
                    cpu = float(cpu_str.strip().replace('%', ''))
                    if 'kafka' in name:
                        _kafka_cpu = cpu
                    elif 'mysql' in name:
                        _mysql_cpu = cpu
        except Exception:
            pass
        time.sleep(3)

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class BridgeHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        global _total_rx, _total_kafka, _total_db

        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        # ── parse ──────────────────────────────────────────────────────────
        try:
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # ── Kafka publish ──────────────────────────────────────────────────
        try:
            _producer.produce(KAFKA_TOPIC, value=body)
            _producer.poll(0)
            with _lock:
                _total_kafka += 1
        except Exception as e:
            print(f'[BRIDGE] Kafka error: {e}')

        # ── MySQL insert ───────────────────────────────────────────────────
        ddc_id        = next((k for k in payload if k not in ('myuuid', 'measured_time')), '')
        measured_time = payload.get('measured_time', '')
        t0 = time.perf_counter()
        try:
            conn, cur = _get_db()
            cur.execute(
                'INSERT INTO telemetry_log (ddc_id, measured_time, payload_json) VALUES (%s, %s, %s)',
                (ddc_id, measured_time, body.decode('utf-8', errors='replace'))
            )
            conn.commit()
            latency_ms = (time.perf_counter() - t0) * 1000
            with _lock:
                _total_db += 1
                _db_latency_ms.append(latency_ms)
        except Exception as e:
            print(f'[BRIDGE] MySQL error: {e}')

        with _lock:
            _total_rx += 1

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, fmt, *args):
        pass   # suppress per-request access log

# ---------------------------------------------------------------------------
# Stats printer + timeline recorder
# ---------------------------------------------------------------------------
def _stats_loop():
    global _total_rx, _total_kafka, _total_db
    last_rx = 0
    while True:
        time.sleep(STATS_INTERVAL)
        now     = time.time()
        elapsed = int(now - _start_time)

        with _lock:
            rx_now  = _total_rx
            db_now  = _total_db
            lats    = list(_db_latency_ms)

        delta       = rx_now - last_rx
        rate        = delta / STATS_INTERVAL
        avg_lat     = sum(lats) / len(lats) if lats else 0
        sys_cpu     = psutil.cpu_percent()
        proc_ram    = psutil.Process().memory_info().rss / (1024 * 1024)

        snap = {
            'elapsed': elapsed,
            'rate': round(rate, 2),
            'total_rx': rx_now,
            'total_db': db_now,
            'avg_db_lat_ms': round(avg_lat, 2),
            'sys_cpu': sys_cpu,
            'proc_ram': round(proc_ram, 1),
            'kafka_cpu': round(_kafka_cpu, 1),
            'mysql_cpu': round(_mysql_cpu, 1),
        }
        _timeline.append(snap)
        last_rx = rx_now

        print(
            f"[{elapsed:>5}s] RX:{rx_now:>6} | {rate:>5.1f} msg/s | "
            f"DB lat:{avg_lat:>6.1f}ms | SysCPU:{sys_cpu:>5.1f}% | "
            f"KafkaCPU:{_kafka_cpu:>5.1f}% | MySQLCPU:{_mysql_cpu:>5.1f}% | "
            f"RAM:{proc_ram:.1f}MB"
        )

        with _lock:
            _db_latency_ms.clear()

# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------
def generate_report(total_duration: float):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)

    total_rx    = _timeline[-1]['total_rx']  if _timeline else 0
    total_db    = _timeline[-1]['total_db']  if _timeline else 0
    avg_rate    = sum(s['rate']          for s in _timeline) / len(_timeline) if _timeline else 0
    peak_rate   = max(s['rate']          for s in _timeline) if _timeline else 0
    avg_sys     = sum(s['sys_cpu']       for s in _timeline) / len(_timeline) if _timeline else 0
    peak_sys    = max(s['sys_cpu']       for s in _timeline) if _timeline else 0
    avg_kafka   = sum(s['kafka_cpu']     for s in _timeline) / len(_timeline) if _timeline else 0
    peak_kafka  = max(s['kafka_cpu']     for s in _timeline) if _timeline else 0
    avg_mysql   = sum(s['mysql_cpu']     for s in _timeline) / len(_timeline) if _timeline else 0
    peak_mysql  = max(s['mysql_cpu']     for s in _timeline) if _timeline else 0
    avg_lat     = sum(s['avg_db_lat_ms'] for s in _timeline) / len(_timeline) if _timeline else 0
    peak_lat    = max(s['avg_db_lat_ms'] for s in _timeline) if _timeline else 0

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('# Scenario 4 - Real Stack Stress Test Report\n')
        f.write('### GL PBS Engineering - Full End-to-End Test\n\n')
        f.write(f'**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'**Duration:** {total_duration:.1f}s\n\n')

        f.write('## 1. Stack Under Test\n\n')
        f.write('| Layer | Detail |\n| :--- | :--- |\n')
        f.write('| BACnet Simulators | 11 DDCs via bacnet_name_launcher.py |\n')
        f.write('| BACnet Reader | bacnet_reader.py with COV filter (3%) |\n')
        f.write('| Bridge | kafka_bacnet_bridge.py (HTTP -> Kafka + MySQL) |\n')
        f.write('| Kafka Topic | pbs.telemetry.real |\n')
        f.write('| MySQL DB | gl_pbs_stress_test.telemetry_log |\n\n')

        f.write('## 2. Performance Results\n\n')
        f.write('| Metric | Value |\n| :--- | :--- |\n')
        f.write(f'| Total Messages Received | {total_rx:,} |\n')
        f.write(f'| Total DB Rows Written | {total_db:,} |\n')
        f.write(f'| Average Rate | {avg_rate:.2f} msg/s |\n')
        f.write(f'| Peak Rate | {peak_rate:.2f} msg/s |\n')
        f.write(f'| Test Duration | {total_duration:.1f}s |\n\n')

        f.write('## 3. Resource Utilization\n\n')
        f.write('| Resource | Average | Peak |\n| :--- | :--- | :--- |\n')
        f.write(f'| System CPU (host) | {avg_sys:.1f}% | {peak_sys:.1f}% |\n')
        f.write(f'| Kafka Container CPU | {avg_kafka:.1f}% | {peak_kafka:.1f}% |\n')
        f.write(f'| MySQL Container CPU | {avg_mysql:.1f}% | {peak_mysql:.1f}% |\n')
        f.write(f'| MySQL Write Latency | {avg_lat:.1f}ms avg | {peak_lat:.1f}ms peak |\n\n')

        f.write('## 4. Comparison vs Kafka-Only Tests\n\n')
        f.write('| Scenario | Source | Rate | COV Filter | DB |\n')
        f.write('| :--- | :--- | :--- | :--- | :--- |\n')
        f.write('| 1 - Basic | Direct Kafka producer | 100 msg/s | No | No |\n')
        f.write('| 2 - Scale 10x | Direct Kafka producer | 500 msg/s | No | No |\n')
        f.write('| 3 - Limit | Direct Kafka producer | 5,000 msg/s | No | No |\n')
        f.write(f'| **4 - Real Stack** | BACnet simulators | {avg_rate:.1f} msg/s | Yes (3%) | Yes (MySQL) |\n\n')

        f.write('## 5. Timeline\n\n')
        f.write('| Time (s) | Rate (msg/s) | Sys CPU % | Kafka CPU % | MySQL CPU % | DB Lat (ms) | Total RX |\n')
        f.write('| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n')
        for s in _timeline:
            f.write(
                f"| {s['elapsed']} | {s['rate']:.1f} | {s['sys_cpu']:.1f}% | "
                f"{s['kafka_cpu']:.1f}% | {s['mysql_cpu']:.1f}% | "
                f"{s['avg_db_lat_ms']:.1f} | {s['total_rx']:,} |\n"
            )

    print(f'\n[DONE] Report: {REPORT_FILE}')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global _producer, _db_config, _start_time, _container_polling

    parser = argparse.ArgumentParser()
    parser.add_argument('--http-host',    default='127.0.0.1')
    parser.add_argument('--http-port',    default=8899, type=int)
    parser.add_argument('--kafka',        default='localhost:9092')
    parser.add_argument('--mysql-host',   default='localhost')
    parser.add_argument('--mysql-port',   default=3306, type=int)
    parser.add_argument('--mysql-user',   default='root')
    parser.add_argument('--mysql-pass',   default='admin')
    parser.add_argument('--mysql-db',     default='gl_pbs_stress_test')
    parser.add_argument('--duration',     default=0, type=int)
    args = parser.parse_args()

    _db_config.update({
        'host': args.mysql_host, 'port': args.mysql_port,
        'user': args.mysql_user, 'password': args.mysql_pass,
        'database': args.mysql_db,
    })

    print('=== Kafka BACnet Bridge ===')
    print(f'HTTP   : {args.http_host}:{args.http_port}')
    print(f'Kafka  : {args.kafka}  topic={KAFKA_TOPIC}')
    print(f'MySQL  : {args.mysql_host}:{args.mysql_port}/{args.mysql_db}')
    print()

    # Init Kafka producer
    _producer = _make_producer(args.kafka)

    # Init MySQL (create table)
    _get_db()
    print('[BRIDGE] MySQL table ready.')

    # Background threads
    threading.Thread(target=_poll_container_stats, daemon=True).start()
    threading.Thread(target=_stats_loop, daemon=True).start()

    _start_time = time.time()
    print(f'[BRIDGE] Listening on {args.http_host}:{args.http_port} — Press Ctrl+C to stop.\n')
    print(f'{"Time":>6} | {"RX":>6} | {"msg/s":>7} | {"DB lat":>8} | {"SysCPU":>7} | {"KafkaCPU":>9} | {"MySQLCPU":>9} | RAM')
    print('-' * 95)

    server = HTTPServer((args.http_host, args.http_port), BridgeHandler)
    if args.duration > 0:
        threading.Timer(args.duration, server.shutdown).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[BRIDGE] Stopping...')
    finally:
        _container_polling = False
        _producer.flush()
        duration = time.time() - _start_time
        generate_report(duration)


if __name__ == '__main__':
    main()
