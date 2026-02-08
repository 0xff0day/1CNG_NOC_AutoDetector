import argparse
import json
import os
import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from autodetector.config import load_config
from autodetector.discovery.discover import discover_hosts
from autodetector.detection.os_detect import detect_os
from autodetector.kb.help import render_help
from autodetector.pipeline.orchestrator import run_poll_once
from autodetector.plugin.manager import builtin_plugins_root, init_plugin, list_builtin_plugins, validate_plugin
from autodetector.reporting.generator import generate_reports
from autodetector.scheduler.scheduler import run_scheduler
from autodetector.storage.sqlite_store import SqliteStore


console = Console()


def _env_or_value(v: str) -> str:
    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
        key = v[2:-1]
        return os.environ.get(key, "")
    return v


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nocctl", description="1CNG_NOC_AutoDetector CLI")
    parser.add_argument("--config", required=True, help="Path to YAML config")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Run one poll cycle (collect->analyze->alert)")
    p_scan.add_argument("--deep", action="store_true", help="Run deep-audit command set")
    p_scan.add_argument("--json", action="store_true", help="Print normalized output JSON")

    p_schedule = sub.add_parser("schedule", help="Run scheduler (fast/normal/deep + reports)")

    p_alerts = sub.add_parser("alerts", help="Show recent alerts")
    p_alerts.add_argument("--limit", type=int, default=50)

    p_ack = sub.add_parser("ack", help="Acknowledge an alert")
    p_ack.add_argument("alert_id", help="Alert ID")
    p_ack.add_argument("--note", default="")
    p_ack.add_argument("--by", default="operator", help="Actor name for audit trail")

    p_report = sub.add_parser("report", help="Generate reports on demand")
    p_report.add_argument("--range", dest="range_", default="hour", choices=["hour", "day", "month", "year"])

    p_help = sub.add_parser("help", help="Show CLI help KB per OS/topic")
    p_help.add_argument("os", help="OS/plugin name, e.g. cisco_ios")
    p_help.add_argument("topic", help="Topic, e.g. cpu, disk")

    p_discover = sub.add_parser("discover", help="Discover SSH/Telnet hosts in a CIDR")
    p_discover.add_argument("--cidr", required=True, help="CIDR to scan, e.g. 10.0.0.0/24")
    p_discover.add_argument("--ports", default="22,23", help="Comma-separated ports to scan (default: 22,23)")
    p_discover.add_argument("--timeout", type=float, default=0.4, help="TCP connect timeout seconds")
    p_discover.add_argument("--limit", type=int, default=4096, help="Max hosts to scan")

    p_detect = sub.add_parser("detect-os", help="Detect OS/vendor via safe CLI probes")
    p_detect.add_argument("--host", required=True)
    p_detect.add_argument("--transport", default="ssh", choices=["ssh", "telnet"])
    p_detect.add_argument("--username", required=True)
    p_detect.add_argument("--password", required=True)

    p_plugin = sub.add_parser("plugin", help="Plugin SDK utilities")
    sp = p_plugin.add_subparsers(dest="plugin_cmd", required=True)

    sp_list = sp.add_parser("list", help="List builtin plugins")
    _ = sp_list

    sp_val = sp.add_parser("validate", help="Validate a plugin (maps/schema)")
    sp_val.add_argument("os", help="Plugin OS name")

    sp_init = sp.add_parser("init", help="Create a new plugin skeleton")
    sp_init.add_argument("os", help="New plugin OS name")
    sp_init.add_argument("--dir", default=builtin_plugins_root(), help="Target plugins directory")

    sp_boot = sp.add_parser("bootstrap", help="Create missing skeleton plugins from registry")
    sp_boot.add_argument("--dir", default=builtin_plugins_root(), help="Target plugins directory")

    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    store = SqliteStore(cfg.system.db_path)
    store.migrate()

    if args.cmd == "scan":
        now = datetime.now(timezone.utc)
        results = run_poll_once(cfg, store, now=now, deep=args.deep)
        if args.json:
            console.print_json(json.dumps(results, indent=2, sort_keys=True, default=str))
        else:
            table = Table(title="Poll Results")
            table.add_column("Device")
            table.add_column("Health")
            table.add_column("Alerts")
            for r in results.get("devices", []):
                table.add_row(r.get("device_id", ""), str(r.get("health_score", "")), str(len(r.get("alerts", []))))
            console.print(table)
        return

    if args.cmd == "schedule":
        run_scheduler(cfg, store)
        return

    if args.cmd == "alerts":
        alerts = store.list_alerts(limit=args.limit)
        table = Table(title="Alerts")
        table.add_column("ID")
        table.add_column("Time")
        table.add_column("Severity")
        table.add_column("Device")
        table.add_column("Variable")
        table.add_column("Type")
        table.add_column("Message")
        table.add_column("Ack")
        for a in alerts:
            table.add_row(
                a["id"],
                a["ts"],
                a["severity"],
                a["device_id"],
                a["variable"],
                a["alert_type"],
                a["message"],
                "yes" if a["ack_ts"] else "no",
            )
        console.print(table)
        return

    if args.cmd == "ack":
        store.ack_alert(args.alert_id, note=args.note, actor=args.by)
        console.print(f"Acknowledged alert {args.alert_id}")
        return

    if args.cmd == "report":
        now = datetime.now(timezone.utc)
        out = generate_reports(cfg, store, now=now, range_name=args.range_)
        console.print_json(json.dumps(out, indent=2, sort_keys=True, default=str))
        return

    if args.cmd == "help":
        txt = render_help(cfg, args.os, args.topic)
        sys.stdout.write(txt + "\n")
        return

    if args.cmd == "discover":
        ports = [int(p.strip()) for p in str(args.ports).split(",") if p.strip()]
        found = discover_hosts(args.cidr, ports=ports, timeout_sec=float(args.timeout), limit=int(args.limit))
        table = Table(title="Discovered Hosts")
        table.add_column("Host")
        table.add_column("Port")
        for f in found:
            table.add_row(f["host"], str(f["port"]))
        console.print(table)
        return

    if args.cmd == "detect-os":
        guess = detect_os(host=args.host, transport=args.transport, username=args.username, password=args.password)
        console.print_json(json.dumps(guess, indent=2, sort_keys=True, default=str))
        return

    if args.cmd == "plugin":
        if args.plugin_cmd == "list":
            table = Table(title="Builtin Plugins")
            table.add_column("OS")
            table.add_column("Path")
            for p in list_builtin_plugins():
                table.add_row(p.os_name, p.path)
            console.print(table)
            return

        if args.plugin_cmd == "validate":
            out = validate_plugin(args.os)
            console.print_json(json.dumps(out, indent=2, sort_keys=True, default=str))
            return

        if args.plugin_cmd == "init":
            p = init_plugin(args.dir, args.os)
            console.print(f"Created plugin skeleton: {p}")
            return

        if args.plugin_cmd == "bootstrap":
            import os as _os
            import yaml as _yaml

            reg_path = _os.path.join(args.dir, "_registry.yaml")
            with open(reg_path, "r", encoding="utf-8") as f:
                reg = _yaml.safe_load(f) or {}
            created = 0
            for grp in ["network", "server", "hypervisor"]:
                for os_name in reg.get(grp, []) or []:
                    os_name = str(os_name)
                    pth = _os.path.join(args.dir, os_name)
                    if _os.path.isdir(pth):
                        continue
                    init_plugin(args.dir, os_name)
                    created += 1
            console.print(f"Bootstrapped {created} plugin skeletons")
            return
