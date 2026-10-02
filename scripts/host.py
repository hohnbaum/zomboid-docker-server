"""Host wrapper: Compose transport only; policy remains in pz-ops."""
import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def compose(*args, capture=False, env=None):
    result = subprocess.run(["docker", "compose", *args], cwd=ROOT, env=env,
                            text=True, capture_output=capture)
    if result.returncode:
        raise RuntimeError("COMPOSE_FAILED")
    return result.stdout if capture else None


def offline():
    output = compose("ps", "--all", "--format", "json", capture=True)
    rows = json.loads(output) if output.lstrip().startswith("[") else [json.loads(x) for x in output.splitlines() if x.strip()]
    if any(x.get("Service") in ("pz-server", "pz-ops") and x.get("State") in ("running", "restarting") for x in rows):
        raise RuntimeError("STOP_COMPOSE_SERVICES_BEFORE_OFFLINE_TOOLS")


def tool(action, args, source=None, export=None):
    offline()
    env = os.environ.copy()
    if source:
        env["PZ_IMPORT_SOURCE"] = str(Path(source).resolve(strict=True))
    if export:
        Path(export).mkdir(parents=True, exist_ok=True)
        env["PZ_EXPORT_DIR"] = str(Path(export).resolve())
    # Defaults are private ignored folders. Do not let Compose create the real source.
    for name in ("imports", "exports"):
        (ROOT / name).mkdir(exist_ok=True)
    compose("--profile", "tools", "run", "--rm", "--no-deps", "tools", action, *args, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-secrets", "init-empty", "import", "restore", "export", "legacy-import", "logs", "job",
        "status", "health", "players", "save", "start", "stop", "restart", "install", "update", "workshop-status", "workshop-update",
        "backup", "config-state", "config-commit", "apply-mod-plan", "maintenance", "jobs", "version", "recover", "info", "endpoints"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--source")
    parser.add_argument("--archive")
    parser.add_argument("--backup")
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--confirm-replace", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--type", default="manual")
    parser.add_argument("--reason", default="")
    parser.add_argument("--record")
    parser.add_argument("--plan")
    parser.add_argument("--before")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "init-secrets":
            path = ROOT / "secrets"
            path.mkdir(mode=0o700, exist_ok=True)
            token = path / "api.token"
            if not token.exists():
                fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(secrets.token_urlsafe(48) + "\n")
            (path / "discord.token").touch(mode=0o600, exist_ok=True)
            print("Private secret files initialized; values were not displayed.")
        elif args.action == "logs":
            compose("exec", "-T", "pz-ops", "python", "-c", "from pathlib import Path;print('\n'.join(Path('/pz/logs/game-console.log').read_text(errors='replace').splitlines()[-100:]))")
        elif args.action == "init-empty":
            tool("empty", [])
        elif args.action == "import":
            if not args.source:
                parser.error("import requires --source pointing to a stopped instance directory")
            tool("import", [], source=args.source)
        elif args.action == "restore" and args.archive:
            archive = Path(args.archive).resolve(strict=True)
            tool("restore", ["--archive", archive.name] + (["--confirm-replace"] if args.confirm_replace else []), source=archive.parent)
        elif args.action == "export":
            if not args.backup or not args.output:
                parser.error("export requires --backup NAME and --output FILE.tar.gz")
            output = Path(args.output).resolve()
            tool("export", ["--backup", args.backup, "--output", output.name], export=output.parent)
        elif args.action == "legacy-import":
            if not all((args.source, args.record, args.plan, args.before)):
                parser.error("legacy-import requires --source, --record, --plan and --before")
            values = ["--record", args.record, "--plan", args.plan, "--before", args.before]
            tool("legacy-import", values + (["--activate"] if args.activate else []), source=args.source)
        else:
            values = {}
            if args.action in ("stop", "restart", "update", "workshop-update", "backup"):
                values["force"] = args.force
            if args.action == "backup":
                values["type"] = args.type
            if args.action == "restore":
                values = {"backup": args.backup or args.value, "confirm_replace": args.confirm_replace}
            if args.action == "apply-mod-plan":
                values = {"plan": json.loads(Path(args.plan or args.value or "").read_text(encoding="utf-8-sig")), "apply": args.apply}
            if args.action == "maintenance":
                if args.value not in ("on", "off"):
                    parser.error("maintenance requires on or off")
                values = {"enabled": args.value == "on", "reason": args.reason}
            cmd = ["exec", "-T", "pz-ops", "python", "-m", "pzops.cli", args.action, "--args", json.dumps(values)]
            if args.action == "job":
                cmd += ["--job", args.value or ""]
            if args.detach:
                cmd.append("--detach")
            compose(*cmd)
    except (RuntimeError, OSError, ValueError):
        print("Command failed. Check Compose state and the structured private job error.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
