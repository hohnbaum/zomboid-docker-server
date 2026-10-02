import argparse
import json
import sys
import time
import uuid
from pzops.api_client import Client
from pzops.core import READ_ACTIONS, JOB_FIELDS
from pzops.util import PZError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=sorted(READ_ACTIONS | set(JOB_FIELDS) | {"ping", "job"}))
    parser.add_argument("--args", default="{}")
    parser.add_argument("--job")
    parser.add_argument("--detach", action="store_true")
    args = parser.parse_args()
    try:
        client = Client(url="http://127.0.0.1:8080")
        if args.action in READ_ACTIONS or args.action == "ping":
            result = client.request(args.action)
        elif args.action == "job":
            result = client.request("jobs/" + (args.job or ""))
        else:
            result = client.request("jobs", {"action": args.action, "args": json.loads(args.args), "request_id": uuid.uuid4().hex})
            print(json.dumps({"job": result["id"], "state": result["state"]}), flush=True)
            if not args.detach:
                last = None
                while result["state"] in ("queued", "running"):
                    phase = result.get("phase")
                    if phase != last:
                        print(json.dumps({"job": result["id"], "phase": phase}), flush=True)
                        last = phase
                    time.sleep(2)
                    result = client.request("jobs/" + result["id"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, dict) and result.get("state") in ("failed", "interrupted"):
            sys.exit(1)
    except (PZError, ValueError) as exc:
        print(json.dumps({"error": exc.code if isinstance(exc, PZError) else "INVALID_ARGUMENT"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
