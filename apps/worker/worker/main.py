import logging
import time
import os
from pathlib import Path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("atlas.worker")
    logger.info("Atlas worker is ready")

    while True:
        # This worker currently performs no jobs or database mutations. Keep
        # the H3 pause explicit; future mutation handlers must also acquire the
        # shared normal-operation guard used by the API/domain services.
        state = os.getenv("ATLAS_STATE_DIR")
        if state and (Path(state) / "maintenance.json").exists():
            time.sleep(5)
            continue
        time.sleep(60)


if __name__ == "__main__":
    main()
