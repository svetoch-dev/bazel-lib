import logging
import typing as tp
import json
from libs.py.settings import (
    LOG_LEVEL,
    LOG_HANDLER_TYPE,
    LOG_FORMATTER_TYPE,
    LOG_FORMATTER_FORMAT,
)
from tiny_json_log import JSONFormatter


class Logger:
    def __init__(
        self,
        logger: logging.Logger,
        handler_type: str,
        formatter_type: str,
        fmt: str,
    ) -> None:
        self.logger = logger
        if handler_type == "stream":
            handler = logging.StreamHandler()
        else:
            raise NotImplementedError(f"handler_type {handler_type} unknown")

        if formatter_type == "json":
            formatter = JSONFormatter(fmt)
        elif formatter_type == "cli":
            formatter = logging.Formatter(fmt, style="{")
        else:
            raise NotImplementedError(f"formatter_type {formatter_type} unknown")

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(LOG_LEVEL)

    def debug(self, msg: str, **kwargs: tp.Any) -> None:
        raise NotImplementedError("debug not implemented")

    def error(self, msg: str, **kwargs: tp.Any) -> None:
        raise NotImplementedError("error not implemented")

    def info(self, msg: str, **kwargs: tp.Any) -> None:
        raise NotImplementedError("info not implemented")

    def warning(self, msg: str, **kwargs: tp.Any) -> None:
        raise NotImplementedError("warning not implemented")


class JsonLogger(Logger):
    def __init__(
        self,
        name: str,
        handler_type: str = LOG_HANDLER_TYPE,
        fmt: str = "severity={levelname} src={name} {message}",
        **initial: tp.Any,
    ) -> None:

        logger = logging.getLogger(name)
        logger.propagate = False

        super().__init__(logger, handler_type, "json", fmt)
        self._initial = initial

    def _get_log_msg(self, msg: str, **kwargs: tp.Any) -> str:
        log_entry = {
            "msg": msg,
        }
        log_entry.update(self._initial)
        log_entry.update(kwargs)
        return json.dumps(log_entry)

    def debug(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.debug(self._get_log_msg(msg, **kwargs))

    def error(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.error(self._get_log_msg(msg, **kwargs))

    def info(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.info(self._get_log_msg(msg, **kwargs))

    def warning(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.warning(self._get_log_msg(msg, **kwargs))


class CliLogger(Logger):
    def __init__(
        self,
        name: str,
        handler_type: str = LOG_HANDLER_TYPE,
        fmt: str = "{asctime} {levelname} {message}",
    ) -> None:

        logger = logging.getLogger(name)
        logger.propagate = False

        super().__init__(logger, handler_type, "cli", fmt)

    def debug(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.debug(msg)

    def error(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.error(msg)

    def info(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.info(msg)

    def warning(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.warning(msg)


root_logger = Logger(
    logging.getLogger(), LOG_HANDLER_TYPE, LOG_FORMATTER_TYPE, LOG_FORMATTER_FORMAT
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx._client").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.Bot").setLevel(logging.WARNING)
