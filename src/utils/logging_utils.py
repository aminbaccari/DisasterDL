"""Logging helpers shared by all DisasterAI modules."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a logger writing to the console with ISO-like timestamps."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format=_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    return logging.getLogger(name)


@contextmanager
def timed(timings: dict[str, float], key: str) -> Iterator[None]:
    """Record the elapsed time of the ``with`` block, in milliseconds, into ``timings[key]``."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[key] = (time.perf_counter() - start) * 1000
