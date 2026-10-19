"""Pure checks over a fixture or real ops directory.

Expected layout under --root (all optional; missing = reported):

  jobs.json          list of scheduled jobs
  heartbeat.json     { "sent_at": ISO8601 Z, "pid": optional }
  config.json        { "armed": bool, ... }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Report:
    ok: bool = True
    lines: list[str] = field(default_factory=list)

    def info(self, msg: str) -> None:
        self.lines.append(f"· {msg}")

    def pass_(self, msg: str) -> None:
        self.lines.append(f"✓ {msg}")

    def fail(self, msg: str) -> None:
        self.ok = False
        self.lines.append(f"✗ {msg}")


def _load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(value: str) -> datetime | None:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def crons(root: Path) -> Report:
    r = Report()
    data = _load_json(root / "jobs.json")
    if data is None:
        r.fail("jobs.json missing — cannot inventory scheduler")
        return r

    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        r.fail("jobs.json must be a list or {\"jobs\": [...]}")
        return r

    r.info(f"found {len(jobs)} job(s)")
    owners: dict[str, list[str]] = {}
    enabled_scripts: list[str] = []

    for i, job in enumerate(jobs):
        if not isinstance(job, dict):
            r.fail(f"job[{i}] is not an object")
            continue
        name = str(job.get("name") or job.get("id") or f"job[{i}]")
        enabled = bool(job.get("enabled", True))
        script = str(job.get("script") or job.get("command") or "")
        role = str(job.get("owner_role") or job.get("role") or "side_effect")
        r.info(f"{name}: enabled={enabled} script={script or '(none)'} role={role}")
        if enabled and script:
            enabled_scripts.append(script)
            owners.setdefault(role, []).append(name)

    # Duplicate scripts enabled = classic ghost-cron failure mode
    seen: dict[str, list[str]] = {}
    for job in jobs:
        if not isinstance(job, dict) or not job.get("enabled", True):
            continue
        script = str(job.get("script") or job.get("command") or "")
        name = str(job.get("name") or job.get("id") or "?")
        if script:
            seen.setdefault(script, []).append(name)
    for script, names in seen.items():
        if len(names) > 1:
            r.fail(f"duplicate enabled script `{script}` used by: {', '.join(names)}")

    side = owners.get("side_effect") or owners.get("trading") or []
    if len(side) > 1:
        r.fail(
            f"multiple enabled side-effect owners: {', '.join(side)} "
            "(want exactly one entrypoint that can place orders / send money)"
        )
    elif len(side) == 1:
        r.pass_(f"single side-effect owner: {side[0]}")
    else:
        r.info("no job marked role=side_effect|trading (ok if this root is non-trading)")

    if not enabled_scripts:
        r.info("no enabled jobs with a script field")
    elif r.ok:
        r.pass_("cron inventory looks consistent")
    return r


def heartbeat(root: Path, *, max_age_s: int = 300) -> Report:
    r = Report()
    data = _load_json(root / "heartbeat.json")
    if data is None:
        r.fail("heartbeat.json missing")
        return r
    if not isinstance(data, dict):
        r.fail("heartbeat.json must be an object")
        return r

    sent = data.get("sent_at") or data.get("ts") or data.get("timestamp")
    if not sent:
        r.fail("heartbeat.json has no sent_at/ts field")
        return r
    dt = _parse_time(str(sent))
    if dt is None:
        r.fail(f"cannot parse sent_at: {sent!r}")
        return r

    age = (datetime.now(timezone.utc) - dt).total_seconds()
    pid = data.get("pid")
    extra = f" pid={pid}" if pid is not None else ""
    r.info(f"last heartbeat {age:.0f}s ago{extra}")
    if age > max_age_s:
        r.fail(f"heartbeat stale (>{max_age_s}s) — process may be up but not healthy")
    else:
        r.pass_(f"heartbeat fresh (≤{max_age_s}s)")
    return r


def armed(root: Path) -> Report:
    r = Report()
    data = _load_json(root / "config.json")
    if data is None:
        r.fail("config.json missing — treat as armed=unknown (do not enable side effects)")
        return r
    if not isinstance(data, dict):
        r.fail("config.json must be an object")
        return r

    if "armed" not in data:
        r.fail("config.json has no `armed` boolean — default should be false")
        return r

    val = data["armed"]
    if not isinstance(val, bool):
        r.fail(f"`armed` must be bool, got {type(val).__name__}")
        return r

    if val:
        r.info("armed=true — side effects allowed by config")
        r.pass_("armed flag present (confirm doctor/crons/heartbeat before relying on this)")
    else:
        r.pass_("armed=false — side effects blocked by config")
    return r


def doctor(root: Path, *, max_heartbeat_age_s: int = 300) -> Report:
    r = Report()
    r.info(f"root={root}")
    parts = [crons(root), heartbeat(root, max_age_s=max_heartbeat_age_s), armed(root)]
    for part in parts:
        r.lines.extend(part.lines)
        if not part.ok:
            r.ok = False
    return r
