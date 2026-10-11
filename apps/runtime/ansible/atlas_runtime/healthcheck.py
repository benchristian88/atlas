"""Internal authenticated healthcheck; never prints credential or payload."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from .server import load_secret


def main():
    try:
        secret = load_secret(Path(os.environ["ATLAS_RUNTIME_CONTROL_SECRET_FILE"]))
        request = urllib.request.Request("http://127.0.0.1:8091/v1/health", headers={"Authorization": "Bearer " + secret})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=3) as response:
            healthy = json.loads(response.read(65536))["state"] == "healthy"
        raise SystemExit(0 if healthy else 1)
    except (OSError, ValueError, KeyError):
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
