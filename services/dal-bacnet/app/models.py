"""
Canonical data models — matches 05_CANONICAL_DATA_MODEL.md
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class QualityEnvelope:
    flag: str = "GOOD"          # GOOD | BAD | UNCERTAIN
    score: float = 1.0          # 0.0–1.0
    dq_flags: list[str] = field(default_factory=list)

    def degrade(self, flag_name: str, severity: str = "BAD") -> None:
        self.dq_flags.append(flag_name)
        if severity == "BAD":
            self.flag = "BAD"
            self.score = max(0.0, self.score - 0.5)
        elif severity == "UNCERTAIN" and self.flag == "GOOD":
            self.flag = "UNCERTAIN"
            self.score = max(0.0, self.score - 0.25)


@dataclass
class PointReading:
    point_id: str               # canonical ID = gl_code from CSV
    device_id: str              # DDC ID (e.g. "DDC01")
    tenant_id: str
    measured_at: datetime
    value_num: Optional[float] = None
    value_str: Optional[str] = None
    quality: QualityEnvelope = field(default_factory=QualityEnvelope)

    # BACnet metadata carried through
    object_type: str = ""
    object_instance: int = 0

    def to_kafka_dict(self) -> dict:
        return {
            "point_id":        self.point_id,
            "device_id":       self.device_id,
            "tenant_id":       self.tenant_id,
            "measured_at":     self.measured_at.isoformat(),
            "value_num":       self.value_num,
            "value_str":       self.value_str,
            "quality_flag":    self.quality.flag,
            "quality_score":   round(self.quality.score, 3),
            "dq_flags":        self.quality.dq_flags,
            "object_type":     self.object_type,
            "object_instance": self.object_instance,
        }
