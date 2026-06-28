import logging
import time
from collections.abc import Callable
from typing import Any


Clock = Callable[[], float]


def now(clock: Clock = time.perf_counter) -> float:
    return clock()


def elapsed_ms(start: float, clock: Clock = time.perf_counter) -> int:
    return int((clock() - start) * 1000)


def _format_event(event: str, **fields: Any) -> str:
    parts = [f"event={event}"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    return " ".join(parts)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(_format_event(event, **fields))


def log_debug_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.debug(_format_event(event, **fields))


def log_duration(
    logger: logging.Logger,
    event: str,
    start: float,
    clock: Clock = time.perf_counter,
    **fields: Any,
) -> None:
    log_event(logger, event, elapsed_ms=elapsed_ms(start, clock), **fields)


def log_debug_duration(
    logger: logging.Logger,
    event: str,
    start: float,
    clock: Clock = time.perf_counter,
    **fields: Any,
) -> None:
    log_debug_event(logger, event, elapsed_ms=elapsed_ms(start, clock), **fields)
