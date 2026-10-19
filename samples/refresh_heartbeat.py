#!/usr/bin/env python3
"""Rewrite samples/ok/heartbeat.json to now (UTC)."""
import json
from datetime import datetime, timezone
from pathlib import Path
path = Path(__file__).resolve().parent / "ok" / "heartbeat.json"
path.write_text(
    json.dumps(
        {"sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "pid": 4242},
        indent=2,
    )
    + "\n"
)
print("wrote", path)
