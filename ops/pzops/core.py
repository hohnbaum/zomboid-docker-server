import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pzops import agent_client, backups, rcon
from pzops.ini import Ini
from pzops.mods import Lifecycle, config_check
from pzops.util import FileLock, Layout, PZError, confined, now, read_json, write_json

READ_ACTIONS = {"status", "health", "players", "version", "workshop-status", "config-state", "info", "endpoints", "jobs"}
JOB_FIELDS = {"install": set(), "start": set(), "stop": {"force"}, "restart": {"force"},
              "update": {"force"}, "workshop-update": {"force"}, "backup": {"force", "type"},
              "save": set(), "apply-mod-plan": {"plan", "apply"}, "config-commit": set(),
              "maintenance": {"enabled", "reason"}, "restore": {"backup", "confirm_replace"},
              "export": {"backup", "output"}, "recover": set(), "discord-restart": set()}


def validate_job(action, args):
    if action not in JOB_FIELDS or not isinstance(args, dict) or set(args) - JOB_FIELDS[action]:
        raise PZError("ACTION_NOT_ALLOWED")
    for key in ("force", "apply", "enabled", "confirm_replace"):
        if key in args and not isinstance(args[key], bool):
            raise PZError("INVALID_ARGUMENT")
    if action == "maintenance" and "enabled" not in args:
        raise PZError("INVALID_ARGUMENT")
    if "reason" in args and (not isinstance(args["reason"], str) or len(args["reason"]) > 200):
        raise PZError("INVALID_ARGUMENT")
    if "backup" in args and (not isinstance(args["backup"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", args["backup"])):
        raise PZError("INVALID_BACKUP_NAME")
    if "output" in args:
        # Online export stays private in the backup volume; host export is one-shot tooling.
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.tar\.gz", args["output"]):
            raise PZError("INVALID_EXPORT_NAME")
    if "type" in args and args["type"] not in backups.TYPES:
        raise PZError("BACKUP_TYPE_INVALID")
    if action == "apply-mod-plan":
        from pzops.mods import validate_plan
        validate_plan(args.get("plan"))
    if action in ("restore", "export") and "backup" not in args:
        raise PZError("INVALID_ARGUMENT")


class Operations:
    def __init__(self, layout=None, agent=agent_client.request, rcon_call=rcon.command, sleep=time.sleep):
        self.layout = layout or Layout.environment()
        self.agent = agent
        self.rcon_call = rcon_call
        self.sleep = sleep
        self.mods = Lifecycle(self.layout)
        for path in (self.layout.state, self.layout.backups, self.layout.logs):
            path.mkdir(parents=True, exist_ok=True)

    def intent(self):
        state = read_json(self.layout.state / "intent.json", {})
        if not isinstance(state, dict) or not isinstance(state.get("desired", False), bool):
            raise PZError("INVALID_STATE")
        return state.get("desired", False)

    def set_intent(self, desired):
        write_json(self.layout.state / "intent.json", {"desired": bool(desired), "updated_at": now()})

    def recovery_required(self):
        return any((self.layout.state / name).exists() for name in
                   ("apply-journal.json", "ack-journal.json", "restore-journal.json", "recovery-required.json"))

    def maintenance(self):
        return bool(read_json(self.layout.state / "maintenance.json", {}).get("enabled")) or (self.layout.state / "operation.json").exists()

    def rcon(self, action):
        ini = Ini.read(self.layout.ini)
        return self.rcon_call("pz-server", int(ini.get("RCONPort")), ini.get("RCONPassword"), action)

    def players(self):
        return rcon.parse_players(self.rcon("players"))

    def status(self):
        reasons = []
        try:
            proc = self.agent("status")
        except PZError as exc:
            proc = {"running": False, "launching": False, "udp": [], "generation": None, "version": None, "build": None}
            reasons.append(exc.code)
        ports = [16261, 16262]
        try:
            ini = Ini.read(self.layout.ini)
            ports = [int(ini.get("DefaultPort")), int(ini.get("UDPPort"))]
        except (PZError, ValueError):
            reasons.append("CONFIG_UNAVAILABLE")
        players = None
        names = []
        known = False
        rcon_ok = False
        if proc.get("running"):
            try:
                connected = self.players()
                players, names = connected["count"], connected["names"]
                known = rcon_ok = True
            except PZError as exc:
                reasons.append(exc.code)
        udp = {str(port): port in proc.get("udp", []) for port in ports}
        if proc.get("running") and not all(udp.values()):
            reasons.append("UDP_MISSING_OR_NOT_OWNED")
        ready = bool(proc.get("running") and all(udp.values()) and rcon_ok and known)
        desired = self.intent()
        maintenance = self.maintenance()
        recovery = self.recovery_required()
        if recovery:
            reasons.append("RECOVERY_REQUIRED")
        pending_valid = None
        if self.layout.pending.exists():
            try:
                self.mods.validate()
                pending_valid = True
            except PZError as exc:
                pending_valid = False
                reasons.append(exc.code)
        state = "MAINTENANCE" if maintenance else "READY" if ready else "STARTING_OR_DEGRADED" if proc.get("running") or proc.get("launching") else "DOWN_UNEXPECTED" if desired else "OFFLINE_EXPECTED"
        cat = backups.catalog(self.layout)
        latest = cat[0] if cat else None
        age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(latest["CompletedAt"])).total_seconds() / 3600) if latest else None
        result = {"state": state, "running": bool(proc.get("running")), "launching": bool(proc.get("launching")),
                  "ready": ready, "desired": desired, "maintenance": maintenance, "players": players, "players_known": known,
                  "player_names": names,
                  "rcon": rcon_ok, "udp": udp, "pending": self.layout.pending.exists(), "pending_valid": pending_valid, "recovery_required": recovery,
                  "generation": proc.get("generation"), "agent": proc.get("agent"), "version": proc.get("version"), "build": proc.get("build"),
                  "uptime_seconds": proc.get("uptime_seconds"), "rss_bytes": proc.get("rss_bytes"),
                  "backup": latest["name"] if latest else None, "backup_age_hours": age, "detail": reasons, "sample_time": now(),
                  "filesystem_free_bytes": shutil.disk_usage(self.layout.data).free}
        for name, key in (("memory.current", "ops_cgroup_memory_bytes"), ("memory.max", "ops_cgroup_limit_bytes")):
            try:
                value = (Path("/sys/fs/cgroup") / name).read_text().strip()
                result[key] = int(value) if value != "max" else None
            except (OSError, ValueError):
                result[key] = None
        result["server_cgroup_memory_bytes"] = proc.get("cgroup_memory_bytes")
        try:
            mods = Ini.read(self.layout.ini).mod_state()
            result.update(workshop_count=len(mods["WorkshopItems"]), mod_count=len(mods["Mods"]))
        except PZError:
            pass
        return result

    def workshop(self):
        return self.agent("workshop", timeout=150, ids=Ini.read(self.layout.ini).mod_state()["WorkshopItems"])

    def build_status(self):
        local = self.agent("status").get("build")
        try:
            remote = self.agent("build-query", timeout=200).get("remote_build")
        except PZError:
            remote = None
        return {"local": local, "remote": remote, "available": local != remote if local and remote else None}

    def read(self, action):
        if action not in READ_ACTIONS:
            raise PZError("ACTION_NOT_ALLOWED")
        if action == "status":
            return self.status()
        if action == "health":
            result = self.status()
            result["update"] = self.build_status()
            try:
                result["workshop"] = self.workshop()
            except PZError:
                result["workshop"] = {"State": "unavailable"}
            result["config"] = config_check(self.layout)
            return result
        if action == "players":
            return self.players()
        if action == "version":
            return self.agent("status")
        if action == "workshop-status":
            return self.workshop()
        if action == "config-state":
            return config_check(self.layout)
        if action == "info":
            from pzops.info import settings
            return settings(self.layout)
        if action == "endpoints":
            return {key: os.getenv("PZ_ADVERTISE_" + key.upper(), "") for key in ("lan", "vpn", "public")}
        return [self.public_job(read_json(p)) for p in sorted((self.layout.state / "jobs").glob("*.json"), reverse=True)][:30]

    @staticmethod
    def public_job(job):
        # Never return submitted private file arguments, token material or raw traceback.
        return {k: job[k] for k in ("id", "action", "state", "created_at", "updated_at", "phase", "error", "result") if k in job}

    def wait_ready(self, generation):
        deadline = time.monotonic() + int(os.getenv("PZ_READY_TIMEOUT", "1200"))
        seen = False
        while time.monotonic() < deadline:
            state = self.status()
            if state.get("generation") != generation:
                raise PZError("CHILD_GENERATION_CHANGED")
            seen = seen or state["running"]
            if state["ready"]:
                return state
            if not state["launching"] or (seen and not state["running"]):
                raise PZError("START_PROCESS_EXITED")
            self.sleep(2)
        raise PZError("READINESS_TIMEOUT")

    def stop_game(self, force=False):
        proc = self.agent("status")
        if not proc.get("launching"):
            return
        count = self.players()["count"]
        if count > 0 and not force:
            raise PZError("PLAYERS_CONNECTED")
        self.rcon("save")
        self.sleep(1)
        self.rcon("quit")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if not self.agent("status").get("launching"):
                return
            self.sleep(1)
        raise PZError("STOP_TIMEOUT")

    def start_game(self, job, safety_done=False):
        pending = self.mods.validate()
        before = self.agent("status")
        if before.get("launching"):
            state = self.wait_ready(before["generation"])
            return {"ready": state["ready"], "pending_retained": bool(pending)}
        if not (self.layout.data / ".runtime-ready.json").exists() and not (self.layout.data / ".import-complete.json").exists():
            raise PZError("INITIALIZE_DATA_FIRST")
        if pending and not safety_done:
            backups.create(self.layout, "pre-workshop-update", before.get("version"))
        self.phase(job, "starting")
        launched = self.agent("start", job=job["id"])
        self.wait_ready(launched["generation"])
        self.phase(job, "ready")
        runtime = read_json(self.layout.data / ".runtime-ready.json")
        if runtime and not runtime.get("bootstrap_completed"):
            write_json(self.layout.data / ".runtime-ready.json", {**runtime, "bootstrap_completed": True})
        self.mods.acknowledge(launched["generation"], pending["RecordId"] if pending else None, True)
        return {"ready": True, "generation": launched["generation"]}

    def phase(self, job, phase):
        job.update(phase=phase, updated_at=now())
        write_json(self.layout.state / "jobs" / (job["id"] + ".json"), job)

    def execute(self, job):
        action, args = job["action"], job.get("args", {})
        validate_job(action, args)
        with FileLock(self.layout.state / "lifecycle.guard"):
            if job.get("automatic") and (not self.intent() or self.maintenance() or self.recovery_required()):
                return {"skipped": "AUTOMATIC_STATE_CHANGED"}
            if action != "recover" and self.recovery_required():
                raise PZError("RECOVERY_REQUIRED")
            if action not in ("maintenance", "recover", "stop", "apply-mod-plan", "config-commit", "export", "save") and read_json(self.layout.state / "maintenance.json", {}).get("enabled"):
                raise PZError("OPERATOR_MAINTENANCE")
            write_json(self.layout.state / "operation.json", {"job": job["id"], "action": action, "started_at": now()})
            try:
                return self._execute(job)
            except PZError:
                if action == "update" or action in ("start", "restart", "workshop-update", "backup") and not self.agent("status").get("launching"):
                    self.set_intent(False)
                raise
            finally:
                (self.layout.state / "operation.json").unlink(missing_ok=True)

    def _execute(self, job):
        action, args = job["action"], job.get("args", {})
        force = args.get("force", False)
        self.phase(job, "validating")
        if action == "maintenance":
            write_json(self.layout.state / "maintenance.json", {"enabled": args["enabled"], "reason": args.get("reason", ""), "updated_at": now()})
            return {"maintenance": args["enabled"]}
        if action == "recover":
            if (self.layout.state / "restore-journal.json").exists():
                raise PZError("RESTORE_RECOVERY_REQUIRES_VALIDATED_RESTORE")
            result = self.mods.recover_apply()
            if self.mods.ackjournal.exists():
                state = self.status()
                if not state["ready"]:
                    raise PZError("RECOVERY_FRESH_GENERATION_UNPROVEN")
                result = self.mods.recover_ack(state["generation"])
            self.mods.validate()
            # Interrupted general jobs are never replayed automatically. Recovery is
            # explicit and requires stopped/known state; intent remains false.
            if (self.layout.state / "recovery-required.json").exists():
                if self.agent("status").get("launching") and not self.status()["ready"]:
                    raise PZError("RECOVERY_GAME_STATE_UNPROVEN")
                (self.layout.state / "recovery-required.json").unlink()
            return result
        if action == "save":
            self.rcon("save")
            return {"save_command_sent": True}
        if action == "config-commit":
            return self.mods.commit()
        if action == "apply-mod-plan":
            return self.mods.apply(args["plan"]) if args.get("apply", False) else self.mods.preview(args["plan"])
        if action == "export":
            return backups.export_archive(self.layout, args["backup"], self.layout.backups / "exports" / args.get("output", args["backup"] + ".tar.gz"))
        self.mods.validate()
        proc = self.agent("status")
        was_running = proc.get("launching", False)
        was_desired = self.intent()
        if action == "install":
            if was_running:
                raise PZError("GAME_LIVE")
            self.phase(job, "installing")
            return self.agent("install", timeout=7500, job=job["id"])
        if action == "start":
            self.set_intent(True)
            return self.start_game(job)
        if action == "stop":
            was_desired = self.intent()
            self.set_intent(False)
            self.phase(job, "saving-and-stopping")
            try:
                self.stop_game(force)
            except PZError as exc:
                if exc.code in ("PLAYERS_CONNECTED", "PLAYERS_UNKNOWN", "RCON_UNAVAILABLE", "RCON_AUTH_FAILED"):
                    self.set_intent(was_desired)
                raise
            return {"stopped": True, "desired": False}
        if action == "restore":
            return backups.restore(self.layout, confined(self.layout.backups, args["backup"]), args.get("confirm_replace", False), desired=self.intent(), running=was_running)
        if action == "discord-restart":
            if self.players()["count"] > 0:
                raise PZError("PLAYERS_CONNECTED")
            action = "update" if self.build_status()["available"] is True else "restart"
        if action == "workshop-update" and not was_running:
            raise PZError("WORKSHOP_UPDATE_REQUIRES_RUNNING")
        if action in ("restart", "update", "backup", "workshop-update"):
            backup_type = args.get("type", "manual")
            workshop_before = None
            if action == "restart":
                try:
                    workshop_before = self.workshop()
                except PZError:
                    workshop_before = {"State": "unavailable"}
                change = config_check(self.layout)["state"]
                backup_type = "pre-workshop-update" if self.layout.pending.exists() or change == "workshop" or workshop_before["State"] != "none" else "pre-config-restart" if change != "none" else None
            if action == "workshop-update":
                workshop_before = self.workshop()
                backup_type = "pre-workshop-update"
            if action == "update":
                backup_type = "pre-server-update"
            self.phase(job, "saving-and-stopping")
            self.stop_game(force)
            if action == "restart":
                self.set_intent(True)
            try:
                if backup_type:
                    self.phase(job, "backup")
                    snapshot = backups.create(self.layout, backup_type, proc.get("version"))
                    backups.retention(self.layout)
                else:
                    snapshot = None
            except Exception:
                if action == "backup" and was_running and not self.layout.pending.exists():
                    self.start_game(job, safety_done=True)
                raise
            if action == "update":
                self.phase(job, "installing")
                self.agent("install", timeout=7500, job=job["id"] + "-install")
            result = {"backup": snapshot["name"] if snapshot else None}
            if was_running or action == "restart" or (action == "update" and was_desired):
                result.update(self.start_game(job, safety_done=bool(snapshot)))
            if action == "workshop-update":
                after = self.workshop()
                result.update(before=workshop_before, after=after, unresolved=after["State"] != "none")
            return result
        raise PZError("ACTION_NOT_ALLOWED")

    def automatic(self, submit):
        if not self.intent() or self.maintenance() or self.recovery_required():
            return
        state = self.status()
        if not state["launching"]:
            submit("start", {}, automatic=True)

    def hourly(self, submit):
        if not self.intent() or self.maintenance() or self.recovery_required():
            return
        schedule = read_json(self.layout.state / "schedule.json", {})
        due = not schedule.get("last_build_check") or time.time() - schedule["last_build_check"] >= 21600
        if due:
            update = self.build_status()
            if update["available"]:
                submit("update", {}, automatic=True)
                return
            if update["available"] is False:
                write_json(self.layout.state / "schedule.json", {"last_build_check": time.time()})
        if self.layout.pending.exists():
            try:
                if self.players()["count"] == 0:
                    submit("restart", {}, automatic=True)
            except PZError:
                pass
            return
        age = self.status()["backup_age_hours"]
        if age is None or age >= 24:
            submit("backup", {"type": "daily"}, automatic=True)
