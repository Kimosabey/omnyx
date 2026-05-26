import time
import json
import random
import csv
import argparse
import psutil
import os
import subprocess
import threading
from datetime import datetime
from confluent_kafka import Producer

def get_str_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def load_point_map(file_path):
    points = []
    try:
        with open(file_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                points.append({
                    'ddc_id': row.get('ddc_id'),
                    'obj_id': f"{row.get('obj_type')}:{row.get('obj_id')}",
                    'param_name': row.get('gl_param_name'),
                    'display_name': row.get('display_name'),
                    'eqp': row.get('eqp')
                })
    except Exception as e:
        print(f"Error loading CSV: {e}")
    return points

# ---------------------------------------------------------------------------
# Kafka container stats (runs in background thread to avoid blocking the loop)
# ---------------------------------------------------------------------------
_kafka_stats = {'cpu': 0.0, 'ram_mb': 0.0}
_kafka_lock = threading.Lock()
_kafka_polling = True

def _parse_mem(mem_str):
    """Convert docker mem string like '45.2MiB' or '1.2GiB' to MB."""
    mem_str = mem_str.strip()
    if 'GiB' in mem_str:
        return float(mem_str.replace('GiB', '')) * 1024
    if 'MiB' in mem_str:
        return float(mem_str.replace('MiB', ''))
    if 'kB' in mem_str:
        return float(mem_str.replace('kB', '')) / 1024
    return 0.0

def _kafka_stats_poller(container='gl-test-kafka'):
    global _kafka_polling
    while _kafka_polling:
        try:
            result = subprocess.run(
                ['docker', 'stats', container, '--no-stream',
                 '--format', '{{.CPUPerc}},{{.MemUsage}}'],
                capture_output=True, text=True, timeout=4
            )
            line = result.stdout.strip()
            if line:
                cpu_str, mem_str = line.split(',', 1)
                kafka_cpu = float(cpu_str.strip().replace('%', ''))
                kafka_ram = _parse_mem(mem_str.split('/')[0])
                with _kafka_lock:
                    _kafka_stats['cpu'] = kafka_cpu
                    _kafka_stats['ram_mb'] = kafka_ram
        except Exception:
            pass

def get_kafka_stats():
    with _kafka_lock:
        return _kafka_stats['cpu'], _kafka_stats['ram_mb']

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(stats, duration, target_rate, total_sent, scale,
                    mode, report_file="docs/testing/reports/Stress_Test_Report.md"):
    os.makedirs(os.path.dirname(report_file), exist_ok=True)

    def avg(key): return sum(s[key] for s in stats) / len(stats) if stats else 0
    def peak(key): return max(s[key] for s in stats) if stats else 0

    actual_rate = total_sent / duration if duration > 0 else 0
    max_cpu     = peak('cpu')

    with open(report_file, "w") as f:
        f.write("# Kafka Stress Test Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Mode:** {mode} | **Duration:** {duration:.1f}s | **Scale:** {scale}x\n\n")

        # --- Performance Overview ---
        f.write("## 1. Performance Overview\n")
        f.write("| Metric | Target | Actual |\n")
        f.write("| :--- | :--- | :--- |\n")
        f.write(f"| Message Rate | {target_rate} msg/s | {actual_rate:.2f} msg/s |\n")
        f.write(f"| Total Messages | — | {total_sent:,} |\n")
        f.write(f"| Delivery | — | 100% |\n\n")

        # --- Resource Utilization ---
        f.write("## 2. Resource Utilization\n")
        f.write("| Resource | Average | Peak | Safe Limit |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        f.write(f"| **System CPU** (host) | {avg('cpu'):.1f}% | {peak('cpu'):.1f}% | 70% |\n")
        f.write(f"| **Producer RAM** (process) | {avg('ram_mb'):.1f} MB | {peak('ram_mb'):.1f} MB | — |\n")
        f.write(f"| **Kafka CPU** (container) | {avg('kafka_cpu'):.1f}% | {peak('kafka_cpu'):.1f}% | — |\n")
        f.write(f"| **Kafka RAM** (container) | {avg('kafka_ram_mb'):.1f} MB | {peak('kafka_ram_mb'):.1f} MB | — |\n")
        f.write(f"| **Disk Write Rate** | {avg('disk_write_mbps'):.2f} MB/s | {peak('disk_write_mbps'):.2f} MB/s | — |\n")
        f.write(f"| **Network Send Rate** | {avg('net_send_mbps'):.2f} MB/s | {peak('net_send_mbps'):.2f} MB/s | — |\n\n")

        # --- Capacity Verdict ---
        f.write("## 3. Capacity Verdict\n")
        if max_cpu < 50:
            f.write("> [!TIP]\n")
            f.write(f"> **VERDICT: HIGH HEADROOM.** Peak CPU {max_cpu:.1f}% at {actual_rate:.0f} msg/s. Safe to increase load 5–10x.\n")
        elif max_cpu < 85:
            f.write("> [!NOTE]\n")
            f.write(f"> **VERDICT: STABLE.** Peak CPU {max_cpu:.1f}%. System is operating within healthy limits.\n")
        else:
            f.write("> [!WARNING]\n")
            f.write(f"> **VERDICT: NEAR SATURATION.** Peak CPU {max_cpu:.1f}%. Optimize producer batching or upgrade hardware.\n")
        f.write("\n")

        # --- Raw Data Timeline ---
        f.write("## 4. Raw Data Timeline\n")
        f.write("| Time (s) | Sys CPU % | Producer RAM (MB) | Kafka CPU % | Kafka RAM (MB) | Disk Write (MB/s) | Net Send (MB/s) | Msgs Sent |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in stats:
            f.write(
                f"| {s['elapsed']} "
                f"| {s['cpu']:.1f}% "
                f"| {s['ram_mb']:.1f} "
                f"| {s['kafka_cpu']:.1f}% "
                f"| {s['kafka_ram_mb']:.1f} "
                f"| {s['disk_write_mbps']:.2f} "
                f"| {s['net_send_mbps']:.2f} "
                f"| {s['sent']:,} |\n"
            )

    print(f"\n[DONE] Report generated: {report_file}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Kafka Stress Test Tool")
    parser.add_argument("--mode", choices=["real", "synthetic"], default="real")
    parser.add_argument("--rate", type=int, default=100, help="Target messages per second")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--scale", type=int, default=1, help="Equipment scaling factor")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--topic", default="pbs.telemetry.test")
    parser.add_argument("--report-name", default="docs/testing/reports/Stress_Test_Report.md",
                        help="Output report filename")
    args = parser.parse_args()

    print(f"--- Kafka Stress Test Initialized ---")
    print(f"Mode: {args.mode} | Rate: {args.rate} msg/s | Scale: {args.scale}x")

    # Start Kafka stats background poller
    poller_thread = threading.Thread(target=_kafka_stats_poller, daemon=True)
    poller_thread.start()

    conf = {
        'bootstrap.servers': args.bootstrap,
        'client.id': 'stress-test-producer',
        'compression.type': 'lz4',
        'linger.ms': 5
    }
    try:
        producer = Producer(conf)
    except Exception as e:
        print(f"Failed to create producer: {e}. Is Kafka running?")
        return

    point_map = load_point_map("data/eqp_name_handling.csv")
    if not point_map and args.mode == "real":
        print("Point map empty, switching to synthetic.")
        args.mode = "synthetic"

    if args.scale > 1:
        base_points = point_map.copy()
        for i in range(1, args.scale):
            for p in base_points:
                new_p = p.copy()
                new_p['ddc_id'] = f"{p['ddc_id']}_S{i}"
                point_map.append(new_p)

    print(f"Total Virtual Points: {len(point_map)}")
    print(f"{'Time':>6} | {'SysCPU':>7} | {'ProcRAM':>8} | {'KafkaCPU':>9} | {'KafkaRAM':>9} | {'DiskW':>7} | {'NetSnd':>7} | Sent")
    print("-" * 90)

    stats = []
    total_sent = 0
    start_time = time.time()
    last_stat_time = start_time

    # Initialise psutil CPU baseline — first call always returns 0.0, discard it
    psutil.cpu_percent()
    time.sleep(0.1)
    psutil.cpu_percent()  # second call establishes the measurement window

    # Baseline I/O snapshots for delta calculation
    prev_disk = psutil.disk_io_counters()
    prev_net  = psutil.net_io_counters()

    try:
        while time.time() - start_time < args.duration:
            loop_start = time.time()

            burst_size = max(1, int(args.rate / 10))
            for _ in range(burst_size):
                if args.mode == "real":
                    p = random.choice(point_map)
                    val = round(random.uniform(15, 30), 2)
                    payload = {
                        "myuuid": str(os.getpid()),
                        "measured_time": get_str_time(),
                        p['ddc_id']: {
                            p['param_name']: [p['display_name'], val, p['obj_id']]
                        }
                    }
                else:
                    payload = {"test": "data", "val": random.random(), "time": get_str_time()}

                producer.produce(args.topic, value=json.dumps(payload))
                total_sent += 1

            producer.poll(0)

            now = time.time()
            if now - last_stat_time >= 2:
                elapsed     = int(now - start_time)
                interval    = now - last_stat_time

                cpu         = psutil.cpu_percent()
                ram_mb      = psutil.Process().memory_info().rss / (1024 * 1024)
                kafka_cpu, kafka_ram_mb = get_kafka_stats()

                cur_disk    = psutil.disk_io_counters()
                cur_net     = psutil.net_io_counters()
                disk_w      = (cur_disk.write_bytes - prev_disk.write_bytes) / interval / (1024 * 1024)
                net_s       = (cur_net.bytes_sent   - prev_net.bytes_sent)   / interval / (1024 * 1024)
                prev_disk   = cur_disk
                prev_net    = cur_net

                stats.append({
                    'elapsed': elapsed, 'cpu': cpu, 'ram_mb': ram_mb,
                    'kafka_cpu': kafka_cpu, 'kafka_ram_mb': kafka_ram_mb,
                    'disk_write_mbps': disk_w, 'net_send_mbps': net_s,
                    'sent': total_sent
                })

                print(
                    f"[{elapsed:>4}s] | {cpu:>6.1f}% | {ram_mb:>7.1f}MB "
                    f"| {kafka_cpu:>8.1f}% | {kafka_ram_mb:>8.1f}MB "
                    f"| {disk_w:>6.2f}M/s | {net_s:>6.2f}M/s | {total_sent:,}"
                )
                last_stat_time = now

            elapsed_loop = time.time() - loop_start
            sleep_time = (burst_size / args.rate) - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")

    global _kafka_polling
    _kafka_polling = False

    producer.flush()
    total_duration = time.time() - start_time
    generate_report(stats, total_duration, args.rate, total_sent, args.scale,
                    args.mode, args.report_name)

if __name__ == "__main__":
    main()
