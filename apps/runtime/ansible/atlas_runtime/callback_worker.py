"""Private bounded callback child; fixed Atlas routing and no ambient proxies."""
import json
import sys
import threading

from atlas_runtime.jobs import send_callback, MAX_BATCH_BYTES


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read(MAX_BATCH_BYTES + 8192))
        send_callback(payload["mode"], payload["run_id"], payload["operation"], payload["token"],
            payload["message"], threading.Event())
    except Exception:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
