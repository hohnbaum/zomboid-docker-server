import hmac
import json
import os
import queue
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from pzops.core import Operations, READ_ACTIONS, validate_job
from pzops.util import FileLock, PZError, now, read_json, write_json


class Jobs:
    def __init__(self, ops):
        self.ops = ops
        self.queue = queue.Queue()
        self.submit_lock = threading.Lock()
        self.directory = ops.layout.state / "jobs"
        self.directory.mkdir(exist_ok=True)
        for path in self.directory.glob("*.json"):
            job = read_json(path)
            if job.get("state") in ("running", "queued"):
                job.update(state="interrupted", error="RECOVERY_REQUIRED", updated_at=now())
                write_json(path, job)
                write_json(ops.layout.state / "recovery-required.json", {"interrupted_job": job["id"]})
                ops.set_intent(False)
        (ops.layout.state / "operation.json").unlink(missing_ok=True)
        threading.Thread(target=self.work, daemon=True).start()

    def submit(self, action, args, automatic=False, request_id=None):
        with self.submit_lock:
            return self._submit(action, args, automatic, request_id)

    def _submit(self, action, args, automatic=False, request_id=None):
        validate_job(action, args)
        if automatic and (not self.ops.intent() or self.ops.maintenance() or not self.queue.empty()):
            return None
        ident = request_id or uuid.uuid4().hex
        if not re.fullmatch(r"[a-f0-9]{32}", ident):
            raise PZError("INVALID_JOB_ID")
        path = self.directory / (ident + ".json")
        if path.exists():
            old = read_json(path)
            if old["action"] != action or old.get("args", {}) != args:
                raise PZError("JOB_ID_CONFLICT")
            return self.ops.public_job(old)
        job = {"id": ident, "action": action, "args": args, "state": "queued", "automatic": automatic,
               "created_at": now(), "updated_at": now(), "phase": "queued"}
        write_json(path, job)
        self.queue.put(job)
        return self.ops.public_job(job)

    def work(self):
        while True:
            job = self.queue.get()
            path = self.directory / (job["id"] + ".json")
            try:
                if job.get("automatic") and (not self.ops.intent() or self.ops.maintenance() or self.ops.recovery_required()):
                    job.update(state="skipped", result={"reason": "AUTOMATIC_STATE_CHANGED"})
                else:
                    job.update(state="running")
                    write_json(path, job)
                    result = self.ops.execute(job)
                    job.update(state="complete", result=result)
            except PZError as exc:
                job.update(state="failed", error=exc.code)
            except Exception:
                job.update(state="failed", error="OPERATION_FAILED")
                self.ops.set_intent(False)
                write_json(self.ops.layout.state / "recovery-required.json", {"interrupted_job": job["id"]})
            finally:
                job.update(updated_at=now())
                write_json(path, job)
                self.queue.task_done()

    def get(self, ident):
        if not re.fullmatch(r"[a-f0-9]{32}", ident):
            raise PZError("INVALID_JOB_ID")
        job = read_json(self.directory / (ident + ".json"))
        if not job:
            raise PZError("JOB_NOT_FOUND")
        return self.ops.public_job(job)


def authorized(header, token):
    return isinstance(header, str) and hmac.compare_digest(header, "Bearer " + token)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Requests may contain private values; no default HTTP request logging.

    def response(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass  # Disconnect never cancels a submitted lifecycle job.

    def authenticated(self):
        if not authorized(self.headers.get("Authorization"), self.server.token):
            self.response(401, {"error": "UNAUTHORIZED"})
            return False
        return True

    def do_GET(self):
        if not self.authenticated():
            return
        try:
            action = self.path.strip("/")
            if action == "ping":
                result = {"ok": True}
            elif action.startswith("jobs/"):
                result = self.server.jobs.get(action.split("/", 1)[1])
            elif action in READ_ACTIONS:
                result = self.server.ops.read(action)
            else:
                raise PZError("ACTION_NOT_ALLOWED")
            self.response(200, result)
        except PZError as exc:
            self.response(400, {"error": exc.code})
        except Exception:
            self.response(500, {"error": "READ_FAILED"})

    def do_POST(self):
        if not self.authenticated():
            return
        try:
            if self.path != "/jobs":
                raise PZError("ACTION_NOT_ALLOWED")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 65536:
                raise PZError("REQUEST_TOO_LARGE")
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict) or set(value) - {"action", "args", "request_id"}:
                raise PZError("INVALID_REQUEST")
            result = self.server.jobs.submit(value.get("action"), value.get("args", {}), request_id=value.get("request_id"))
            self.response(202, result)
        except PZError as exc:
            self.response(400, {"error": exc.code})
        except (ValueError, TypeError):
            self.response(400, {"error": "INVALID_REQUEST"})


def scheduler(ops, jobs):
    last_watch = last_health = last_hourly = 0
    while True:
        stamp = time.monotonic()
        try:
            if stamp - last_watch >= 300:
                ops.automatic(jobs.submit)
                last_watch = stamp
            if stamp - last_hourly >= 3600:
                ops.hourly(jobs.submit)
                last_hourly = stamp
            if stamp - last_health >= 120:
                sample = ops.status()
                path = ops.layout.logs / ("health-" + now()[:7] + ".jsonl")
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(sample) + "\n")
                # Monthly files older than 366 days; scoped filename only.
                for old in ops.layout.logs.glob("health-????-??.jsonl"):
                    if time.time() - old.stat().st_mtime > 366 * 86400:
                        old.unlink()
                last_health = stamp
        except Exception:
            # Diagnostics are fixed codes. The next iteration retries; no raw exception.
            pass
        time.sleep(2)


def main():
    os.umask(0o077)
    token = Path("/run/secrets/api_token").read_text().strip()
    if len(token) < 32:
        raise PZError("API_SECRET_MISSING")
    ops = Operations()
    with FileLock(ops.layout.state / "service.guard"):
        jobs = Jobs(ops)
        with ThreadingHTTPServer(("0.0.0.0", 8080), Handler) as server:
            server.ops, server.jobs, server.token = ops, jobs, token
            threading.Thread(target=scheduler, args=(ops, jobs), daemon=True).start()
            server.serve_forever()


if __name__ == "__main__":
    main()
