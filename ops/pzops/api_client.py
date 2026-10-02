import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from pzops.util import PZError


class Client:
    def __init__(self, url=None, token_file="/run/secrets/api_token"):
        self.url = url or os.getenv("PZ_OPS_URL", "http://pz-ops:8080")
        self.token = Path(token_file).read_text().strip()

    def request(self, action, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + "/" + action, data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                code = json.load(exc).get("error", "API_ERROR")
            except (ValueError, OSError):
                code = "API_ERROR"
            # Trust only fixed uppercase error codes from the private service.
            import re
            raise PZError(code if isinstance(code, str) and re.fullmatch(r"[A-Z0-9_]{1,80}", code) else "API_ERROR") from None
        except (OSError, ValueError):
            raise PZError("API_UNAVAILABLE") from None
