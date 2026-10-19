from pathlib import Path
import json
from datetime import datetime, timezone

from agent_ops import checks

ROOT = Path(__file__).resolve().parents[1]
OK = ROOT / "samples" / "ok"
BAD = ROOT / "samples" / "bad"


def test_ok_doctor_green():
    # refresh heartbeat so CI age stays fresh
    (OK / "heartbeat.json").write_text(
        json.dumps(
            {"sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "pid": 1}
        )
    )
    report = checks.doctor(OK)
    assert report.ok, report.lines


def test_bad_doctor_fails_on_duplicate_and_stale():
    report = checks.doctor(BAD, max_heartbeat_age_s=60)
    assert not report.ok
    text = "\n".join(report.lines)
    assert "duplicate" in text
    assert "stale" in text
