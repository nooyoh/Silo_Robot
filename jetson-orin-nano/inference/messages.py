from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

Polygon = list[list[float]]  # [[x0,y0], [x1,y1], ...] 정규화 좌표 0~1


@dataclass(frozen=True)
class Detection:
    x: float
    y: float
    width: float
    height: float
    label: str
    confidence: float
    polygon: Polygon = field(default_factory=list)  # 신규 — crack/corrosion 마스크 윤곽선

    def normalized(self) -> "Detection":
        clamp = lambda value: max(0.0, min(1.0, float(value)))
        x = clamp(self.x)
        y = clamp(self.y)
        poly = [[clamp(px), clamp(py)] for px, py in self.polygon]
        return Detection(
            x=x,
            y=y,
            width=min(clamp(self.width), 1.0 - x),
            height=min(clamp(self.height), 1.0 - y),
            label=self.label,
            confidence=clamp(self.confidence),
            polygon=poly,
        )


def detection_message(detections: Iterable[Detection]) -> dict:
    return {
        "type": "detection",
        "detections": [asdict(item.normalized()) for item in detections],
    }


def hello_message() -> dict:
    return {"type": "hello", "role": "orin"}
