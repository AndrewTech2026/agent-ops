# agent-ops

Small CLI to **doctor** autonomous agent operations before they touch money, DMs, or production.

Born from real failure modes: ghost crons, “process up but no heartbeat”, and kill switches that didn’t block the script the scheduler actually ran.

## Install

```bash
git clone https://github.com/AndrewTech2026/agent-ops.git
cd agent-ops
python3 -m pip install -e .
```

Or run without install:

```bash
python3 -m agent_ops doctor --root samples/ok
```

## Two-minute demo

```bash
# refresh sample heartbeat to "now" (committed timestamp goes stale)
python3 samples/refresh_heartbeat.py

# healthy fixture → exit 0
PYTHONPATH=. python3 -m agent_ops doctor --root samples/ok

# broken fixture → exit 1 (duplicate side-effect cron + stale heartbeat)
PYTHONPATH=. python3 -m agent_ops doctor --root samples/bad
```

## Commands

| Command | What it checks |
|---------|----------------|
| `agent-ops doctor --root DIR` | crons + heartbeat + armed |
| `agent-ops crons --root DIR` | inventory; fails on duplicate enabled scripts / multiple side-effect owners |
| `agent-ops heartbeat --root DIR` | age vs warn/hard thresholds (PID alone is not health) |
| `agent-ops armed --root DIR` | `config.json` has boolean `armed` |
| `agent-ops check-config --root DIR` | optional `protect.json` schema; rejects secret-like keys; requires live reconcile |

Heartbeat thresholds (first match wins): CLI `--max-heartbeat-age` / `--warn-heartbeat-age` → `config.json` → defaults `300` / `120`.

## Expected files under `--root`

```text
jobs.json        # {"jobs":[{"name","enabled","script","owner_role"}, ...]}
heartbeat.json   # {"sent_at":"2026-10-23T10:00:00Z","pid":123}
config.json      # {"armed": false, "heartbeat_max_age_s": 300, "heartbeat_warn_age_s": 120}
protect.json     # optional; stop/TP intent only — never API keys; require_live_reconcile: true
```

Point `--root` at a **sanitized export** of your ops dir, or keep a mirror that your watchdog already writes. Do not commit live API keys.

## Watchdog snippet (macOS)

Generic launchd template that runs `doctor` on an interval — alert on exit ≠ 0, not on “PID exists”:

[`samples/watchdog/`](samples/watchdog/)

## Design rules

1. Missing `armed` ⇒ not safe (fail). Prefer default deny.
2. PID alone is not health — heartbeat age is.
3. Exactly one enabled `owner_role=side_effect` (or `trading`) job.
4. Warn band before hard-stale reduces false “everything is fine” calm.
5. Local protect rules are intent — always reconcile against live open orders.

## Related

- Notes & calendar: [public-lab](https://github.com/AndrewTech2026/public-lab)
- Week 2 note: [process up ≠ healthy](https://github.com/AndrewTech2026/public-lab/blob/main/notes/week2-process-up-not-healthy.md)
- Week 3 note: [local state vs live orders](https://github.com/AndrewTech2026/public-lab/blob/main/notes/week3-local-state-vs-live-orders.md)
- Hardening checklist: [agent-hardening.md](https://github.com/AndrewTech2026/public-lab/blob/main/checklists/agent-hardening.md)

## Status

`v0.1.2` — `check-config` for protect.json (no keys; require live reconcile). Stdlib only, fixture-tested.
