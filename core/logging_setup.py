"""Logging configuration for MetGuardian.

I funnel everything under the ``metguardian`` logger namespace (the scanner,
the state machine, the scheduler, ...) into a rotating file plus the console.
Child loggers like ``metguardian.state_machine`` propagate up to here, so
configuring the parent once captures the whole application.

The file log is where I look for software anomalies: every ``try/except`` that
catches an unexpected error logs it here with a full traceback.
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

__version__ = "1.0.0"

# Default log location: <project_root>/logs/metguardian.log
# (this file lives in core/, one level below the project root, hence parents[1].)
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"

# Root namespace for all application loggers.
LOGGER_NAME = "metguardian"

# Rotation settings: keep the log bounded so it never fills the disk.
MAX_BYTES = 1_000_000   # ~1 MB per file
BACKUP_COUNT = 5        # keep 5 rotated files


def setup_logging(log_dir=None, level=logging.INFO):
    """Configure the ``metguardian`` logger with a rotating file and console.

    Safe to call more than once: if the logger already has handlers I leave it
    as is and just return it, so I never attach duplicate handlers.

    Args:
        log_dir: folder for the log file. Defaults to ``<project_root>/logs``.
        level: logging level (default ``logging.INFO``).

    Returns:
        logging.Logger: the configured ``metguardian`` logger.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # Already configured -> do not add handlers again.
    if logger.handlers:
        return logger

    folder = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    folder.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        folder / "metguardian.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # I handle propagation myself; do not also bubble up to the root logger.
    logger.propagate = False

    return logger
