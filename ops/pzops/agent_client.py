import json
import socket
import sys
from pzops.util import PZError


def request(action, timeout=10, **args):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect("/pz/control/agent.sock")
            sock.sendall(json.dumps({"action": action, **args}).encode() + b"\n")
            with sock.makefile("rb") as stream:
                raw = stream.readline(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise PZError("AGENT_RESPONSE_TOO_LARGE")
                result = json.loads(raw)
        if not result.get("ok"):
            raise PZError(result.get("error", "AGENT_ERROR"))
        return result["result"]
    except (OSError, ValueError):
        raise PZError("AGENT_UNAVAILABLE") from None


if __name__ == "__main__":
    try:
        print(json.dumps(request(sys.argv[1] if len(sys.argv) > 1 else "ping")))
    except PZError as exc:
        print(exc.code)
        sys.exit(1)
