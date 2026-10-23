"""agent-ops — small doctor CLI for autonomous agent operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_ops import __version__
from agent_ops import checks


def _print_report(report: checks.Report) -> int:
    for line in report.lines:
        print(line)
    if report.ok:
        print("\nOK — doctor green")
        return 0
    print("\nFAIL — fix items above before arming side effects")
    return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    report = checks.doctor(
        root,
        max_heartbeat_age_s=args.max_heartbeat_age,
        warn_heartbeat_age_s=args.warn_heartbeat_age,
    )
    return _print_report(report)


def cmd_crons(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    report = checks.crons(root)
    return _print_report(report)


def cmd_heartbeat(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    report = checks.heartbeat(
        root,
        max_age_s=args.max_heartbeat_age,
        warn_age_s=args.warn_heartbeat_age,
    )
    return _print_report(report)


def cmd_armed(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    report = checks.armed(root)
    return _print_report(report)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-ops",
        description="Doctor cron inventory, heartbeats, and armed/kill switches for agent stacks.",
    )
    p.add_argument("--version", action="version", version=f"agent-ops {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_root(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--root",
            default=".",
            help="Directory with jobs.json / heartbeat.json / config.json (default: .)",
        )

    def add_hb(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--max-heartbeat-age",
            type=int,
            default=None,
            help="Hard-fail age in seconds (default: config heartbeat_max_age_s or 300)",
        )
        sp.add_argument(
            "--warn-heartbeat-age",
            type=int,
            default=None,
            help="Warn band in seconds (default: config or min(120, hard))",
        )

    d = sub.add_parser("doctor", help="Run all checks")
    add_root(d)
    add_hb(d)
    d.set_defaults(func=cmd_doctor)

    c = sub.add_parser("crons", help="Inventory scheduler jobs; flag duplicates / missing owner")
    add_root(c)
    c.set_defaults(func=cmd_crons)

    h = sub.add_parser("heartbeat", help="Check heartbeat freshness (PID alone is not enough)")
    add_root(h)
    add_hb(h)
    h.set_defaults(func=cmd_heartbeat)

    a = sub.add_parser("armed", help="Show whether side effects are armed")
    add_root(a)
    a.set_defaults(func=cmd_armed)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
