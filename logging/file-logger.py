"""
Logging to file with indented messages
"""

import logging


class LogFileFormatter(logging.Formatter):
    def __init__(self):
        # The fmt string ensures that exception info and tracebacks will still
        # be added to the message according to the default log formatter
        # behaviour
        super().__init__(fmt='%(message)s')

    def format(self, rec):
        prefix = f'[{rec.levelname}] {self.formatTime(rec)} {rec.name}: '
        indent = '\n' + (' ' * len(prefix))
        msg = super().format(rec)
        return prefix + msg.replace('\n', indent)
