"""A fixed-operation Linux PZ child owner. No shell/path endpoint."""
import json
import os
import re
import signal
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from pzops.ini import Ini
from pzops.util import FileLock, PZError, file_hash, identifier, now, read_json, write_json
from pzops import rcon
from pzops.redact import pump
from pzops.logs import startup_issue

APP = Path("/pz/app")
DATA = Path("/pz/data")
CONTROL = Path("/pz/control")
LOGS = Path("/pz/logs")


class Agent:
    def __init__(self):
        self.servername = identifier(os.getenv("PZ_SERVER_NAME", "pztest"))
        self.identity = uuid.uuid4().hex
        self.child = None
        self.generation = None
        self.child_log = None
        self.mutex = threading.RLock()
        self.actions = {}
        self.log_offset = None
        self.app_lock = None
        self.data_lock = None

    def process(self):
        if self.child is None or self.child.poll() is not None:
            return None
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                pid = int(entry.name)
                text = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
                executable = os.readlink(entry / "exe")
                if os.getpgid(pid) == self.child.pid and (executable == str(APP / "ProjectZomboid64") or b"zombie.network.GameServer" in text):
                    return pid
            except (OSError, ProcessLookupError):
                continue
        return None

    def installed(self):
        manifest = APP / "steamapps/appmanifest_380870.acf"
        text = manifest.read_text() if manifest.exists() else ""
        m = re.search(r'"buildid"\s+"(\d+)"', text)
        evidence = read_json(APP / ".pz-install.json", {})
        build = m[1] if m else None
        incomplete = (APP / ".pz-installing.json").exists()
        version = evidence.get("version") if evidence.get("version_build") == build else None
        # Only this agent's current launch establishes version evidence. Copied logs
        # and previous build logs cannot satisfy the imported-world gate.
        path = LOGS / "game-console.log"
        if not incomplete and self.log_offset is not None and path.exists():
            with path.open("rb") as stream:
                stream.seek(self.log_offset)
                content = stream.read(8 * 1024 * 1024).decode(errors="replace")
            found = re.findall(r'\bversion=(\d+\.\d+\.\d+)\b', content)
            # PZ emits this during its own initialization, before loading mods.
            # Later mod/library release messages must not replace that identity.
            if found and (version != found[0] or evidence.get("version_build") != build):
                version = found[0]
                evidence.update(version=version, version_build=build, verified_at=now(), generation=self.generation,
                                version_evidence="current Linux launcher startup")
                write_json(APP / ".pz-install.json", evidence)
        return {"installed": (APP / "start-server.sh").is_file(), "build": build,
                "version": None if incomplete else version, "installation_incomplete": incomplete,
                "agent": self.identity, "evidence": evidence}

    def udp(self, pid):
        inodes = set()
        try:
            for fd in (Path("/proc") / str(pid) / "fd").iterdir():
                target = os.readlink(fd)
                m = re.fullmatch(r"socket:\[(\d+)\]", target)
                if m:
                    inodes.add(m[1])
        except OSError:
            return []
        ports = set()
        for name in ("udp", "udp6"):
            try:
                for line in (Path("/proc") / str(pid) / "net" / name).read_text().splitlines()[1:]:
                    cols = line.split()
                    if cols[9] in inodes:
                        ports.add(int(cols[1].split(":")[1], 16))
            except (OSError, ValueError, IndexError):
                continue
        return sorted(ports)

    def status(self):
        if self.app_lock and (self.child is None or self.child.poll() is not None):
            self.app_lock.__exit__()
            self.app_lock = None
            if self.data_lock:
                self.data_lock.__exit__()
                self.data_lock = None
        pid = self.process()
        try:
            cgroup_memory = int(Path("/sys/fs/cgroup/memory.current").read_text())
        except (OSError, ValueError):
            cgroup_memory = None
        rss = None
        uptime = None
        if pid:
            try:
                s = (Path("/proc") / str(pid) / "status").read_text()
                rss = int(re.search(r"VmRSS:\s+(\d+)", s)[1]) * 1024
                start_ticks = (Path("/proc") / str(pid) / "stat").read_text().split(") ", 1)[1].split()[19]
                uptime = float(Path("/proc/uptime").read_text().split()[0]) - int(start_ticks) / os.sysconf("SC_CLK_TCK")
            except (OSError, ValueError, TypeError):
                pass
        return {"running": bool(pid), "launching": bool(self.child and self.child.poll() is None),
                "pid": pid, "generation": self.generation, "agent": self.identity,
                "udp": self.udp(pid) if pid else [], "rss_bytes": rss, "uptime_seconds": uptime,
                "cgroup_memory_bytes": cgroup_memory,
                'startup_issue': startup_issue(LOGS / 'game-console.log', self.log_offset) if self.child and self.child.poll() is not None else None,
                **self.installed()}

    def install(self, job):
        # An explicitly shared app volume cannot be updated while another project
        # owns its native runtime. This lock is also held for the Java child's life.
        with FileLock(APP / ".app-runtime.guard"):
            return self._install(job)

    def _install(self, job):
        if self.child and self.child.poll() is None:
            raise PZError("GAME_LIVE")
        if job in self.actions:
            return self.actions[job]
        previous = self.installed()
        self.log_offset = None
        write_json(APP / ".pz-installing.json", {"job": job, "started_at": now()})
        log = LOGS / ("steam-install-" + job + ".log")
        args = ["/opt/steamcmd/steamcmd.sh", "+force_install_dir", str(APP), "+login", "anonymous",
                "+app_info_update", "1", "+app_update", "380870", "+quit"]
        with log.open("wb") as stream:
            proc = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=7200)
        text = log.read_text(errors="replace")
        if proc.returncode or not re.search(r"Success! App '380870' (?:fully installed|already up to date)", text):
            raise PZError("STEAM_INSTALL_FAILED")
        if not (APP / "start-server.sh").is_file():
            raise PZError("LINUX_LAUNCHER_MISSING")
        version = None
        for name in ("pzversion", "version.txt", "media/lua/shared/defines.lua"):
            path = APP / name
            if path.is_file():
                m = re.search(r"\b(42\.\d+\.\d+)\b", path.read_text(errors="replace"))
                if m:
                    version = m[1]
                    break
        evidence = {"installed_at": now(), "command": args, "version": version,
                    "launcher": "start-server.sh", "launcher_sha256": file_hash(APP / "start-server.sh")}
        if previous.get("version") and previous["build"] == self.installed()["build"]:
            evidence.update(version=previous["version"], version_build=previous["build"],
                            version_evidence=previous["evidence"].get("version_evidence"))
        write_json(APP / ".pz-install.json", evidence)
        (APP / ".pz-installing.json").unlink()
        self.actions[job] = self.installed()
        return self.actions[job]

    def start(self, job):
        current = self.status()
        if current["launching"]:
            return current
        if job in self.actions:
            raise PZError("JOB_ALREADY_STARTED")
        if current["installation_incomplete"]:
            raise PZError("APP_INSTALL_INCOMPLETE")
        if not current["installed"]:
            raise PZError("APP_NOT_INSTALLED")
        imported = read_json(DATA / ".import-complete.json") or read_json(DATA / ".migration-gate.json")
        if imported:
            required = imported.get("required_version")
            if required != "42.21.0" or current["version"] != required:
                raise PZError("BLOCKED_VERSION")
            pristine = read_json(DATA / ".pristine-verified.json")
            if not isinstance(pristine, dict) or not isinstance(pristine.get("backup"), str) or not re.fullmatch(r"[a-f0-9]{64}", pristine.get("manifest_hash", "")):
                raise PZError("PRISTINE_BACKUP_REQUIRED")
        ini = Ini.read(DATA / "Server" / (self.servername + ".ini"))
        if int(ini.get("DefaultPort")) != 16261 or int(ini.get("UDPPort")) != 16262:
            raise PZError("INTERNAL_PORT_MAPPING_MISMATCH")
        heap = os.getenv("PZ_HEAP", "6g")
        if not re.fullmatch(r"[1-9]\d*[mg]", heap):
            raise PZError("INVALID_HEAP")
        self.generation = uuid.uuid4().hex
        package = read_json(APP / "ProjectZomboid64.json")
        package["vmArgs"] = [v for v in package["vmArgs"] if not v.startswith(("-Xms", "-Xmx"))] + ["-Xms" + heap, "-Xmx" + heap]
        self.app_lock = FileLock(APP / ".app-runtime.guard")
        self.app_lock.__enter__()
        try:
            self.data_lock = FileLock(DATA / ".game-runtime.guard")
            self.data_lock.__enter__()
        except Exception:
            self.app_lock.__exit__()
            self.app_lock = None
            raise
        write_json(APP / "ProjectZomboid64.json", package)
        self.child_log = (LOGS / "game-console.log").open("ab", buffering=0)
        self.log_offset = self.child_log.tell()
        args = ["/bin/bash", str(APP / "start-server.sh"), "-servername", self.servername,
                "-cachedir=" + str(DATA)]
        # A first synthetic admin password is delivered via stdin, never a process argument.
        try:
            self.child = subprocess.Popen(args, cwd=APP, stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except Exception:
            self.app_lock.__exit__()
            self.app_lock = None
            self.data_lock.__exit__()
            self.data_lock = None
            raise
        admin = DATA / ".bootstrap-admin.secret"
        secrets = [ini.get(key, "").encode() for key in ("Password", "RCONPassword")]
        if admin.exists():
            secrets.append(admin.read_text().strip().encode())
        threading.Thread(target=pump, args=(self.child.stdout, self.child_log, secrets), daemon=True).start()
        if admin.exists() and not read_json(DATA / ".runtime-ready.json", {}).get("bootstrap_completed"):
            self.child.stdin.write((admin.read_text().strip() + "\n") .encode() * 2)
            self.child.stdin.flush()
        write_json(CONTROL / "child.json", {"generation": self.generation, "agent": self.identity,
                                           "job": job, "started_at": now(), "launcher": "start-server.sh",
                                           "heap": heap})
        self.actions[job] = self.generation
        return self.status()

    def build_query(self):
        if self.child and self.child.poll() is None:
            # Metadata query is safe while game runs, but shares the Steam mutex.
            pass
        result = subprocess.run(["/opt/steamcmd/steamcmd.sh", "+login", "anonymous", "+app_info_update", "1",
                                 "+app_info_print", "380870", "+quit"], capture_output=True, timeout=180)
        text = result.stdout.decode(errors="replace")
        m = re.search(r'"branches"\s*\{.*?"public"\s*\{.*?"buildid"\s*"(\d+)"', text, re.S)
        return {"remote_build": m[1] if result.returncode == 0 and m else None, "sample_time": now()}

    def workshop(self, ids):
        if not isinstance(ids, list) or len(ids) > 2000 or any(not isinstance(x, str) or not re.fullmatch(r"\d+", x) for x in ids):
            raise PZError("INVALID_WORKSHOP_IDS")
        root = APP / "steamapps/workshop"
        acf = root / "appworkshop_108600.acf"
        text = acf.read_text() if acf.exists() else ""
        installed = text.split('"WorkshopItemsInstalled"', 1)[-1].split('"WorkshopItemDetails"', 1)[0] if '"WorkshopItemsInstalled"' in text else ""
        local = {m[1]: m[2] for m in re.finditer(r'"(\d+)"\s*\{(.*?)\}', installed, re.S)}
        remote = {}
        available = True
        for off in range(0, len(ids), 50):
            batch = ids[off:off+50]
            body = {"itemcount": str(len(batch)), **{f"publishedfileids[{i}]": v for i, v in enumerate(batch)}}
            try:
                req = urllib.request.Request("https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                                             urllib.parse.urlencode(body).encode())
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.load(response)
                for entry in result["response"]["publishedfiledetails"]:
                    remote[str(entry["publishedfileid"])] = entry
            except (OSError, ValueError, KeyError):
                available = False
        items = []
        for ident in ids:
            body = local.get(ident, "")
            t = re.search(r'"timeupdated"\s*"(\d+)"', body)
            m = re.search(r'"manifest"\s*"(\d+)"', body)
            detail = remote.get(ident, {})
            if not (root / "content/108600" / ident).is_dir() or not t:
                state = "Missing"
            elif detail.get("result") != 1 or not detail.get("time_updated"):
                state = "Unknown"
            else:
                state = "Update" if int(detail["time_updated"]) > int(t[1]) else "Current"
            items.append({"Id": ident, "Title": str(detail.get("title", ""))[:200], "Status": state,
                          "LocalTime": int(t[1]) if t else None, "RemoteTime": detail.get("time_updated"),
                          "Manifest": m[1] if m else None})
        counts = {k: sum(x["Status"] == k for x in items) for k in ("Current", "Update", "Missing", "Unknown")}
        state = "update" if counts["Update"] or counts["Missing"] else "unavailable" if counts["Unknown"] or not available else "none"
        return {"State": state, "Configured": len(ids), "Items": items, **counts, "sample_time": now()}

    def dispatch(self, request):
        action = request.get("action")
        allowed = {"ping": {"action"}, "status": {"action"}, "start": {"action", "job"},
                   "install": {"action", "job"}, "build-query": {"action"}, "workshop": {"action", "ids"}}
        if action not in allowed or set(request) - allowed[action]:
            raise PZError("ACTION_NOT_ALLOWED")
        if action == "ping":
            return {"agent": self.identity}
        if action == "status":
            return self.status()
        with self.mutex:
            if action in ("install", "start"):
                job = identifier(request.get("job"))
                return self.install(job) if action == "install" else self.start(job)
            if action == "build-query":
                return self.build_query()
            return self.workshop(request.get("ids"))

    def shutdown(self):
        if self.child is None or self.child.poll() is not None:
            return
        try:
            ini = Ini.read(DATA / "Server" / (self.servername + ".ini"))
            port, password = int(ini.get("RCONPort")), ini.get("RCONPassword")
            rcon.command("127.0.0.1", port, password, "save")
            time.sleep(1)
            rcon.command("127.0.0.1", port, password, "quit")
            self.child.wait(timeout=60)
        except (PZError, subprocess.TimeoutExpired, OSError, ValueError):
            # Docker's outer grace timeout can eventually terminate the container;
            # do not hide this as a verified clean shutdown or kill the child here.
            while self.child.poll() is None:
                time.sleep(1)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            raw = self.rfile.readline(65537)
            if len(raw) > 65536:
                raise PZError("REQUEST_TOO_LARGE")
            result = self.server.agent.dispatch(json.loads(raw))
            output = {"ok": True, "result": result}
        except PZError as exc:
            output = {"ok": False, "error": exc.code}
        except Exception:
            output = {"ok": False, "error": "AGENT_ERROR"}
        try:
            self.wfile.write(json.dumps(output).encode() + b"\n")
        except OSError:
            pass


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main():
    os.umask(0o077)
    CONTROL.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    with FileLock(CONTROL / "agent.guard"):
        path = CONTROL / "agent.sock"
        if path.exists():
            path.unlink()
        agent = Agent()
        with Server(str(path), Handler) as server:
            server.agent = agent
            os.chmod(path, 0o660)
            def shutdown(*_):
                threading.Thread(target=server.shutdown, daemon=True).start()
            signal.signal(signal.SIGTERM, shutdown)
            signal.signal(signal.SIGINT, shutdown)
            server.serve_forever()
            agent.shutdown()


if __name__ == "__main__":
    main()
