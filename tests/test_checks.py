from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

from agent_ops import checks

ROOT = Path(__file__).resolve().parents[1]
OK = ROOT / "samples" / "ok"
BAD = ROOT / "samples" / "bad"


def _fresh(age_s: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_ok_doctor_green():
    (OK / "heartbeat.json").write_text(
        json.dumps({"sent_at": _fresh(0), "pid": 1})
    )
    report = checks.doctor(OK)
    assert report.ok, report.lines


def test_bad_doctor_fails_on_duplicate_and_stale():
    report = checks.doctor(BAD, max_heartbeat_age_s=60)
    assert not report.ok
    text = "\n".join(report.lines)
    assert "duplicate" in text
    assert "stale" in text


def test_warn_band_still_ok():
    (OK / "heartbeat.json").write_text(
        json.dumps({"sent_at": _fresh(150), "pid": 99})
    )
    report = checks.heartbeat(OK, max_age_s=300, warn_age_s=120)
    assert report.ok, report.lines
    text = "\n".join(report.lines)
    assert "aging" in text
    assert "pid=99" in text


def test_stale_mentions_pid_still_listed():
    (OK / "heartbeat.json").write_text(
        json.dumps({"sent_at": _fresh(999), "pid": 42})
    )
    report = checks.heartbeat(OK, max_age_s=300)
    assert not report.ok
    text = "\n".join(report.lines)
    assert "pid=42 still listed" in text
