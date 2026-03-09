import logging
import typing as tp
import json
import sys
from libs.py.settings import log_settings
from tiny_json_log import JSONFormatter


class BaseLogger:
    def __init__(
        self,
        logger: logging.Logger,
        handler_type: str,
        formatter_type: str,
        fmt: str,
    ) -> None:
        self.logger = logger
        self.logger.setLevel(log_settings.log_level)
        self.logger.propagate = False

        if handler_type == "stream":
            handler = logging.StreamHandler(stream=sys.stdout)
        else:
            raise NotImplementedError(f"handler_type {handler_type} unknown")

        if formatter_type == "json":
            formatter = JSONFormatter(fmt, merge_message=True)
        elif formatter_type == "cli":
            formatter = logging.Formatter(fmt, style="{")
        else:
            raise NotImplementedError(f"formatter_type {formatter_type} unknown")

        handler.setFormatter(formatter)

        self.logger.handlers.clear()
        self.logger.addHandler(handler)

    def debug(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.debug(msg)

    def error(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.error(msg)

    def info(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.info(msg)

    def warning(self, msg: str, **kwargs: tp.Any) -> None:
        self.logger.warning(msg)


class JsonLogger(BaseLogger):
    def __init__(
        self,
        name: str,
        handler_type: str = "stream",
        fmt: str = "severity={levelname} src={name} {message}",
        **initial: tp.Any,
    ) -> None:
        logger = logging.getLogger(name)

        super().__init__(logger, handler_type, "json", fmt)
        self._initial = initial

    def _get_log_msg(self, msg: str, **kwargs: tp.Any) -> str:
        log_entry = {
            "message": msg,
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


class CliLogger(BaseLogger):
    def __init__(
        self,
        name: str,
        handler_type: str = "stream",
        fmt: str = "{asctime} {levelname} {message}",
    ) -> None:
        logger = logging.getLogger(name)
        super().__init__(logger, handler_type, "cli", fmt)


class RootLogger(BaseLogger):
    def __init__(
        self,
        handler_type: str = "stream",
        fmt_type: str = "json",
        fmt: str = "severity={levelname} src={name} {message}",
    ) -> None:
        super().__init__(logging.getLogger(), handler_type, fmt_type, fmt)
