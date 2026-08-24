import logging
import os
import sys

_COLORS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{_RESET}"
        record.asctime = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"{record.asctime} | {level} | {self.service_name} | {record.name} | {record.getMessage()}"


def setup_logging(service_name: str) -> logging.Logger:
    env = os.getenv("ENVIRONMENT", "development")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if env == "development" else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColorFormatter(service_name))
    root.handlers = [handler]
    return root
