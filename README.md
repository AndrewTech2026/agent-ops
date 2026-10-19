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
| `agent-ops heartbeat --root DIR` | `heartbeat.json` fresher than `--max-heartbeat-age` (default 300s) |
| `agent-ops armed --root DIR` | `config.json` has boolean `armed` |

## Expected files under `--root`

```text
jobs.json        # {"jobs":[{"name","enabled","script","owner_role"}, ...]}
heartbeat.json   # {"sent_at":"2026-10-19T07:00:00Z","pid":123}
config.json      # {"armed": false}
```

Point `--root` at a **sanitized export** of your ops dir, or keep a mirror that your watchdog already writes. Do not commit live API keys.

## Design rules

1. Missing `armed` ⇒ not safe (fail). Prefer default deny.
2. PID alone is not health — heartbeat age is.
3. Exactly one enabled `owner_role=side_effect` (or `trading`) job.

## Related

- Notes & calendar: [public-lab](https://github.com/AndrewTech2026/public-lab)
- Hardening checklist: [agent-hardening.md](https://github.com/AndrewTech2026/public-lab/blob/main/checklists/agent-hardening.md)

## Status

`v0.1.0` — stdlib only, fixture-tested. Week-2 calendar may add generic watchdog snippets.
