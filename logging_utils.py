import sys
from typing import Iterable, Sequence

from loguru import logger


def _mask_value(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) <= 6:
        return "***"
    return f"{trimmed[:3]}***{trimmed[-3:]}"


def redact(text: str, secrets: Sequence[str]) -> str:
    masked = text
    for secret in secrets:
        if not secret:
            continue
        masked = masked.replace(secret, _mask_value(secret))
    return masked


def configure_logger(debug: bool, secrets: Iterable[str]):
    """
    Configure loguru to avoid leaking sensitive values.

    The sink manually formats logs and redacts known secrets before writing to stdout.
    """
    logger.remove()
    secret_values = [value for value in secrets if value]
    level = "DEBUG" if debug else "INFO"

    def _sink(message):
        record = message.record
        timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S%z")
        base = f"[{timestamp}] {record['level'].name:<8} {record['message']}"
        safe_message = redact(base, secret_values)
        sys.stdout.write(safe_message + "\n")

    logger.add(_sink, level=level, backtrace=False, diagnose=debug)
