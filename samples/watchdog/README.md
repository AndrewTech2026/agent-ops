# Generic launchd heartbeat watchdog (macOS)

This is a **template**. It does not talk to exchanges. It only runs `agent-ops doctor`
on a local ops export directory and writes the exit code somewhere your notifier can read.

## Install (edit paths first)

1. Copy `com.example.agent-ops-doctor.plist` to `~/Library/LaunchAgents/`
2. Replace `REPLACE_WITH_ABS_PATH_TO_AGENT_OPS` and `REPLACE_WITH_ABS_PATH_TO_OPS_ROOT`
3. Load:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.agent-ops-doctor.plist
```

## Unload

```bash
launchctl bootout gui/$(id -u)/com.example.agent-ops-doctor
```

## What “healthy” means here

- Process can be up and still fail doctor (stale heartbeat, duplicate cron, armed missing).
- Prefer alerting on **doctor exit ≠ 0**, not on “PID exists”.
