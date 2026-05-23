from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils import EscalationLogEntry


def ensure_log_file(path: str | Path) -> Path:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text("[]", encoding="utf-8")
    return log_path


def append_escalation_log(path: str | Path, entry: EscalationLogEntry | dict[str, Any]) -> None:
    log_path = ensure_log_file(path)

    if isinstance(entry, EscalationLogEntry):
        new_entry = entry.model_dump()
    else:
        new_entry = dict(entry)

    try:
        existing = json.loads(log_path.read_text(encoding="utf-8") or "[]")
        if not isinstance(existing, list):
            existing = []
    except json.JSONDecodeError:
        existing = []

    existing.append(new_entry)
    temp_path = log_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    temp_path.replace(log_path)

