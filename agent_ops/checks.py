"""Pure checks over a fixture or real ops directory.

Expected layout under --root (all optional; missing = reported):

  jobs.json          list of scheduled jobs
  heartbeat.json     { "sent_at": ISO8601 Z, "pid": optional }
  config.json        { "armed": bool, "heartbeat_max_age_s": optional, ... }
  protect.json      optional protect-rules schema (no exchange keys)
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

    def warn(self, msg: str) -> None:
        self.lines.append(f"! {msg}")

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


def _heartbeat_thresholds(
    root: Path,
    *,
    max_age_s: int | None,
    warn_age_s: int | None,
) -> tuple[int, int | None]:
    """CLI overrides win; else config.json; else defaults (300 / 120)."""
    cfg = _load_json(root / "config.json")
    cfg_max = None
    cfg_warn = None
    if isinstance(cfg, dict):
        if "heartbeat_max_age_s" in cfg:
            cfg_max = int(cfg["heartbeat_max_age_s"])
        hb = cfg.get("heartbeat")
        if isinstance(hb, dict):
            if "max_age_s" in hb:
                cfg_max = int(hb["max_age_s"])
            if "warn_age_s" in hb:
                cfg_warn = int(hb["warn_age_s"])
        if "heartbeat_warn_age_s" in cfg:
            cfg_warn = int(cfg["heartbeat_warn_age_s"])

    hard = max_age_s if max_age_s is not None else (cfg_max if cfg_max is not None else 300)
    warn = warn_age_s if warn_age_s is not None else cfg_warn
    if warn is None:
        warn = min(120, hard) if hard > 120 else None
    if warn is not None and warn >= hard:
        warn = None
    return hard, warn


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


def heartbeat(
    root: Path,
    *,
    max_age_s: int | None = None,
    warn_age_s: int | None = None,
) -> Report:
    r = Report()
    hard, warn = _heartbeat_thresholds(root, max_age_s=max_age_s, warn_age_s=warn_age_s)
    r.info(f"thresholds: warn={warn if warn is not None else 'off'}s hard={hard}s")

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

    # PID alone is not health — only age matters for pass/fail
    if age > hard:
        r.fail(
            f"heartbeat stale (>{hard}s) — process may be up but not healthy"
            + (f" (pid={pid} still listed)" if pid is not None else "")
        )
    elif warn is not None and age > warn:
        r.warn(f"heartbeat aging (>{warn}s, ≤{hard}s) — investigate before it goes hard-stale")
        r.pass_(f"heartbeat within hard limit (≤{hard}s)")
    else:
        r.pass_(f"heartbeat fresh (≤{warn if warn is not None else hard}s)")
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




# Keys that must never appear in a public/sanitized protect file
_FORBIDDEN_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "secret",
    "private_key",
    "privkey",
    "seed",
    "mnemonic",
    "wallet",
    "password",
    "passphrase",
    "authorization",
)


def _walk_forbidden_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower().replace("-", "_")
            here = f"{path}.{k}"
            for frag in _FORBIDDEN_KEY_FRAGMENTS:
                if frag in key:
                    hits.append(here)
                    break
            hits.extend(_walk_forbidden_keys(v, here))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_walk_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def check_config(root: Path) -> Report:
    """Validate optional protect.json — local protect rules, never live exchange truth."""
    r = Report()
    path = root / "protect.json"
    data = _load_json(path)
    if data is None:
        r.info("protect.json missing — skip (ok if this root has no protect rules)")
        return r
    if not isinstance(data, dict):
        r.fail("protect.json must be an object")
        return r

    forbidden = _walk_forbidden_keys(data)
    if forbidden:
        r.fail(
            "protect.json contains secret-like keys (sanitize before commit): "
            + ", ".join(forbidden[:8])
        )

    if "armed" in data and not isinstance(data["armed"], bool):
        r.fail("`armed` in protect.json must be bool")

    if "require_live_reconcile" not in data:
        r.warn("missing require_live_reconcile — default should be true (local state ≠ live orders)")
    elif data["require_live_reconcile"] is not True:
        r.fail("require_live_reconcile must be true — never trust local stops alone")
    else:
        r.pass_("require_live_reconcile=true")

    symbols = data.get("symbols")
    if symbols is None:
        r.info("no symbols map (ok for empty template)")
    elif not isinstance(symbols, dict):
        r.fail("`symbols` must be an object")
    else:
        for sym, rule in symbols.items():
            if not isinstance(rule, dict):
                r.fail(f"symbols.{sym} must be an object")
                continue
            for side in ("stop_loss", "take_profit"):
                if side not in rule:
                    continue
                block = rule[side]
                if not isinstance(block, dict):
                    r.fail(f"symbols.{sym}.{side} must be an object")
                    continue
                if "type" not in block or "value" not in block:
                    r.fail(f"symbols.{sym}.{side} needs type + value")
                elif not isinstance(block["value"], (int, float)):
                    r.fail(f"symbols.{sym}.{side}.value must be number")
            if "max_notional_usd" in rule and not isinstance(rule["max_notional_usd"], (int, float)):
                r.fail(f"symbols.{sym}.max_notional_usd must be number")
        if r.ok:
            r.pass_(f"protect schema ok for {len(symbols)} symbol(s)")

    if r.ok and not forbidden:
        if "require_live_reconcile" in data and data["require_live_reconcile"] is True:
            pass  # already passed above
        elif not any(line.startswith("✗") for line in r.lines):
            r.pass_("protect.json sanitized shape looks ok")
    return r


def doctor(
    root: Path,
    *,
    max_heartbeat_age_s: int | None = None,
    warn_heartbeat_age_s: int | None = None,
) -> Report:
    r = Report()
    r.info(f"root={root}")
    parts = [
        crons(root),
        heartbeat(root, max_age_s=max_heartbeat_age_s, warn_age_s=warn_heartbeat_age_s),
        armed(root),
        check_config(root),
    ]
    for part in parts:
        r.lines.extend(part.lines)
        if not part.ok:
            r.ok = False
    return r
