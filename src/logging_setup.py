"""src/logging_setup.py — structured logging to data/logs/app.log."""
import logging
import logging.handlers
import pathlib
import sys

LOG_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_FILE = LOG_DIR / "app.log"

_FMT = "%(asctime)s %(levelname)-8s %(name)-30s %(message)s"
_DATE = "%Y-%m-%dT%H:%M:%S"


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logger: file handler (rotating) + stderr handler."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return  # already configured (idempotent)

    formatter = logging.Formatter(_FMT, datefmt=_DATE)

    # Rotating file handler — 5 MB per file, keep 3
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler — INFO and above
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("Logging setup OK — writing to %s", LOG_FILE)
    log.debug("Debug messages go only to file")
    print(f"Log file: {LOG_FILE}")

