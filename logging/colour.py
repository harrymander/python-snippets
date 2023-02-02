"""
Coloured logging

Add to a logging handler with setFormatter() method.
"""

import logging


class ColorLogFormatter(logging.Formatter):
    """
    Adapted from https://stackoverflow.com/a/56944256
    """

    default = ''
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    COLORS = {
        logging.DEBUG: grey,
        logging.INFO: default,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def __init__(self):
        # The fmt string ensures that exception info and tracebacks will still
        # be added to the message according to the default log formatter
        # behaviour
        super().__init__(fmt='%(message)s')

    def format(self, record):
        msg = super().format(record)
        if record.levelno == logging.DEBUG:
            msg = '[DEBUG] ' + msg
        return f'{self.COLORS[record.levelno]}{msg}{self.reset}'
