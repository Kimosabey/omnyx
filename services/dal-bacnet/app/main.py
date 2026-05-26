"""
OMNYX DAL-BACnet — entry point
Loop: poll all DDCs → DQ Tier 1 → Kafka telemetry.raw
"""
import logging
import signal
import sys
import time
from contextlib import suppress

from .config import settings
from .csv_loader import load_point_map
from .publisher import KafkaPublisher
from .reader import load_controller_map, poll_device, start_bacnet_thread, stop_bacnet
from .metrics import start_metrics, devices_active, devices_offline, read_latency

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
)
log = logging.getLogger("main")

_running = True


def _shutdown(sig, frame):
    global _running
    log.info("Signal %s received, shutting down", sig)
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("DAL-BACnet starting — tenant=%s", settings.tenant_id)

    # Start Prometheus metrics endpoint
    start_metrics(settings.metrics_port)
    log.info("Metrics on :%d", settings.metrics_port)

    # Load point map from CSV
    point_map, ddc_order = load_point_map(settings.csv_path)
    if not point_map:
        log.error("No points loaded from CSV, exiting")
        sys.exit(1)

    # Start BACnet event loop thread
    app = start_bacnet_thread()

    # Kafka publisher
    publisher = KafkaPublisher()

    # Per-DDC previous-values dict for CoV tracking
    prev_values: dict[str, dict] = {ddc: {} for ddc in ddc_order}

    # Heartbeat tracking
    last_heartbeat = time.time()

    log.info("Starting poll loop — interval=%.1fs, DDCs=%s", settings.poll_interval_s, ddc_order)

    while _running:
        loop_start = time.time()
        force_all = (loop_start - last_heartbeat) >= settings.heartbeat_s

        # Load fresh controller map each cycle (launcher may rewrite it)
        controller_map = load_controller_map(settings.bacnet_ini)
        if not controller_map:
            log.warning("Controller map empty, waiting...")
            time.sleep(settings.poll_interval_s)
            continue

        active = 0
        offline = 0

        for ddc_id in ddc_order:
            address = controller_map.get(ddc_id)
            if not address:
                log.debug("No address for %s in controller map", ddc_id)
                offline += 1
                continue

            cov_threshold = 0.0 if force_all else settings.cov_threshold_pct

            try:
                readings = poll_device(
                    app=app,
                    ddc_id=ddc_id,
                    address=address,
                    point_map=point_map.get(ddc_id, {}),
                    tenant_id=settings.tenant_id,
                    prev_values=prev_values[ddc_id],
                    cov_threshold=cov_threshold,
                )
                if readings:
                    publisher.publish_batch(readings)
                    log.debug("Published %d readings from %s", len(readings), ddc_id)
                active += 1
            except Exception as exc:
                log.error("Poll failed for %s: %s", ddc_id, exc)
                offline += 1

        if force_all:
            last_heartbeat = time.time()

        elapsed = time.time() - loop_start
        read_latency.observe(elapsed)
        devices_active.set(active)
        devices_offline.set(offline)

        log.info("Cycle done — active=%d offline=%d elapsed=%.2fs", active, offline, elapsed)

        sleep_time = max(0.0, settings.poll_interval_s - elapsed)
        time.sleep(sleep_time)

    # Graceful shutdown
    log.info("Shutting down publisher and BACnet")
    with suppress(Exception):
        publisher.close()
    stop_bacnet()
    log.info("DAL-BACnet stopped")


if __name__ == "__main__":
    main()
