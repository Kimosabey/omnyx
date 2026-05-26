"""
Load eqp_name_handling.csv and build two lookup maps:
  point_map[ddc_id][(obj_type, obj_id)] = PointMeta
  ddc_ids: ordered list of unique DDC IDs
"""
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("csv_loader")


@dataclass
class PointMeta:
    ddc_id: str
    obj_type: str           # 'analogInput', 'binaryInput', etc.
    obj_id: int
    eqp: str                # equipment code (C0, B0, etc.)
    gl_param_name: str      # internal param name
    display_name: str       # human label
    gl_code: str            # canonical OMNYX point_id
    skip: bool


def load_point_map(csv_path: str) -> tuple[dict, list[str]]:
    """
    Returns:
        point_map: {ddc_id: {(obj_type, obj_id): PointMeta}}
        ddc_order: ordered list of unique DDC IDs (first appearance)
    """
    point_map: dict[str, dict[tuple, PointMeta]] = {}
    ddc_order: list[str] = []

    path = Path(csv_path)
    if not path.exists():
        log.error("CSV not found: %s", csv_path)
        return point_map, ddc_order

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skip = row.get("skip", "").strip().lower() in ("1", "true", "yes", "skip")
            if skip:
                continue

            ddc_id   = row["ddc_id"].strip()
            obj_type = row["obj_type"].strip()
            obj_id   = int(row["obj_id"].strip())
            gl_code  = row.get("gl_code", "").strip()

            if not gl_code:
                continue  # no canonical ID, skip

            if ddc_id not in point_map:
                point_map[ddc_id] = {}
                ddc_order.append(ddc_id)

            meta = PointMeta(
                ddc_id=ddc_id,
                obj_type=obj_type,
                obj_id=obj_id,
                eqp=row.get("eqp", "").strip(),
                gl_param_name=row.get("gl_param_name", "").strip(),
                display_name=row.get("display_name", "").strip(),
                gl_code=gl_code,
                skip=False,
            )
            point_map[ddc_id][(obj_type, obj_id)] = meta

    total = sum(len(v) for v in point_map.values())
    log.info("Loaded %d points across %d DDCs from %s", total, len(ddc_order), csv_path)
    return point_map, ddc_order
