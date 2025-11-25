import logging
from logging import LogRecord
from typing import Any
from logging_loki import LokiHandler
import inspect

from src.settings import settings


class PrettyFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: LogRecord) -> str:
        record_message = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        return f"{color}[{record.levelname:<8}]{reset} {record_message}"


def setup_logger() -> logging.Logger:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        PrettyFormatter("%(asctime)s | %(module)s:%(lineno)d | %(message)s")
    )

    logger = logging.getLogger("synapse-logger")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    if settings.LOKI_ENDPOINT:
        loki_handler = LokiHandler(
            url=settings.LOKI_ENDPOINT, tags={"application": "synapse"}, version="1"
        )
        logger.addHandler(loki_handler)

    return logger


base_logger = setup_logger()


class SynapseLogger:
    def __init__(self) -> None:
        self._logger = base_logger

    def _get_class_name(self) -> str | None:
        stack = inspect.stack()
        if len(stack) > 2:
            frame = stack[2].frame
            self_obj = frame.f_locals.get("self", None)
            if self_obj:
                return type(self_obj).__name__
            module = frame.f_globals.get("__name__")
            return module
        return None

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        class_name = self._get_class_name()
        extra = kwargs.pop("extra", {})

        tags = extra.get("tags", {})
        if class_name:
            tags["class"] = class_name

        extra["tags"] = tags
        self._logger.log(level, message, extra=extra, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, **kwargs)
