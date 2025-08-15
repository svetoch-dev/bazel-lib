import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_HANDLER_TYPE = os.getenv("LOG_HANDLER_TYPE", "stream")
LOG_FORMATTER_TYPE = os.getenv("LOG_FORMATTER_TYPE", "json")
LOG_FORMATTER_FORMAT = os.getenv(
    "LOG_FORMATTER_FORMAT", "severity={levelname} logger={name} {message}"
)
