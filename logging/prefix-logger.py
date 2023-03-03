"""
Context manager for prefixing log messages
"""

from contextlib import contextmanager
import logging
from typing import Callable, cast

import pytest


logger = logging.getLogger(__name__)


@contextmanager
def prefix_logging(prefix: str):
    try:
        logger = logging.getLogger()
        formatters = [h.formatter for h in logger.handlers]
        format_methods = [f.format if f else None for f in formatters]
        for formatter, old_format in zip(formatters, format_methods):
            if formatter is not None and old_format is not None:
                def format(record: logging.LogRecord) -> str:
                    # Cast to avoid mypy error (not sure why there is one)
                    return prefix + cast(
                        Callable[[logging.LogRecord], str],
                        old_format
                    )(record)

                setattr(formatter, 'format', format)
        yield
    finally:
        for formatter, old_method in zip(formatters, format_methods):
            if formatter is not None:
                setattr(formatter, 'format', old_method)


def log_func(msg):
    logger.info(msg)


def test_indent(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    logger.info('Hello, World!')
    with prefix_logging('  '):
        logger.info('Should be indented...')
        with prefix_logging('  '):
            logger.info('Double indented')
        log_func('From a function')
    logger.info('Should be unindented')

    assert caplog.text == """
INFO Hello, World!
  INFO Should be indented...
    INFO Double indented
  INFO From a function
INFO Should be unindented
""".lstrip()
