from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class JsonlDetectionLogger:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, frame_id: int, message: dict) -> Path:
        now = datetime.now(timezone.utc)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"detections-{now.astimezone().date().isoformat()}.jsonl"
        record = {
            "timestamp": now.isoformat(),
            "frame_id": frame_id,
            **message,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return path
