import logging

import click


class ClickLogHandler(logging.Handler):
    """
    Logging handler that uses click.secho to print coloured log messages to a
    standard stream (stderr by default).

    ANSI colour codes will be stripped out by click if the output stream does
    not support them (e.g. redirecting to file).

    Log message formatting can be overridden by passing a dict to the
    'click_style' kwarg of the log function; e.g.:

        logger.info(
            "Bold green text with red background!",
            click_style=dict(fg="green", bg="red", bold=True),
        )
    """

    def __init__(self, *, err: bool = True):
        self.__err = err
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        fmt: dict | None = getattr(record, "click_style", None)
        if fmt is None:
            color = {
                logging.DEBUG: "white",
                logging.WARNING: "yellow",
                logging.ERROR: "red",
                logging.CRITICAL: "red",
            }.get(record.levelno, None)
            fmt = dict(fg=color, bold=record.levelno >= logging.CRITICAL)

        click.secho(self.format(record), err=self.__err, **fmt)


# Example usage: just prints the coloured message to stderr
def setup_click_logger(level: int) -> None:
    handler = ClickLogHandler(err=True)
    handler.setFormatter(logging.Formatter(fmt="%(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
