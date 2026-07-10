import logging
import time


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("atlas.worker")
    logger.info("Atlas worker is ready")

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
