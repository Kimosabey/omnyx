"""
PostgreSQL writer — persists PointReadings to telemetry.readings
and audit events to audit.events.
Uses psycopg2 with execute_values for batch inserts.
"""
import logging
import time
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

from .config import settings
from . import metrics

log = logging.getLogger("writer")

_TELEMETRY_INSERT = """
    INSERT INTO telemetry.readings
        (measured_at, point_id, device_id, tenant_id,
         value_num, value_str, quality_flag, quality_score, dq_flags, payload)
    VALUES %s
    ON CONFLICT DO NOTHING
"""

_AUDIT_INSERT = """
    INSERT INTO audit.events (actor, action, target, payload, tenant_id)
    VALUES %s
"""


class DBWriter:
    def __init__(self) -> None:
        self._conn = None
        self._connect()

    def _connect(self) -> None:
        retries = 0
        while True:
            try:
                self._conn = psycopg2.connect(settings.postgres_url)
                self._conn.autocommit = False
                log.info("Connected to Postgres")
                return
            except psycopg2.OperationalError as exc:
                retries += 1
                wait = min(2 ** retries, 30)
                log.warning("Postgres connect failed (%s), retry in %ds", exc, wait)
                time.sleep(wait)

    def _ensure_connection(self) -> None:
        try:
            self._conn.isolation_level  # ping
        except Exception:
            log.warning("Lost Postgres connection, reconnecting")
            self._connect()

    def write_readings(self, messages: list[dict]) -> int:
        """Write a batch of PointReading dicts to telemetry.readings."""
        if not messages:
            return 0

        rows = []
        for m in messages:
            rows.append((
                m.get("measured_at"),
                m.get("point_id"),
                m.get("device_id"),
                m.get("tenant_id", settings.tenant_id),
                m.get("value_num"),
                m.get("value_str"),
                m.get("quality_flag", "GOOD"),
                m.get("quality_score", 1.0),
                m.get("dq_flags", []),
                psycopg2.extras.Json({
                    "object_type":     m.get("object_type"),
                    "object_instance": m.get("object_instance"),
                }),
            ))

        self._ensure_connection()
        t0 = time.perf_counter()
        try:
            with self._conn.cursor() as cur:
                execute_values(cur, _TELEMETRY_INSERT, rows, page_size=500)
            self._conn.commit()
            elapsed = time.perf_counter() - t0
            metrics.write_latency.observe(elapsed)
            for m in messages:
                metrics.rows_written.labels(
                    tenant_id=m.get("tenant_id", settings.tenant_id),
                    quality_flag=m.get("quality_flag", "GOOD"),
                ).inc()
            log.debug("Wrote %d readings in %.3fs", len(rows), elapsed)
            return len(rows)
        except Exception as exc:
            self._conn.rollback()
            metrics.write_errors.inc()
            log.error("Write failed: %s", exc)
            raise

    def write_audit(self, events: list[dict]) -> None:
        """Write audit events to audit.events."""
        if not events:
            return
        rows = [
            (
                e.get("actor", "system"),
                e.get("action", "unknown"),
                e.get("target"),
                psycopg2.extras.Json(e.get("payload", {})),
                e.get("tenant_id", settings.tenant_id),
            )
            for e in events
        ]
        self._ensure_connection()
        try:
            with self._conn.cursor() as cur:
                execute_values(cur, _AUDIT_INSERT, rows)
            self._conn.commit()
            metrics.audit_rows_written.inc(len(rows))
        except Exception as exc:
            self._conn.rollback()
            log.error("Audit write failed: %s", exc)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
