"""
Basic example showing logging from a single point of origin (e.g. to play nice
with tqdm progress bars) with concurrent.futures.

Real code would need more work e.g. to handle exceptions in the remote
processes.

This code is fairly fragile - occassionally it will hang on joining the
executor_runner thread...
"""

import argparse
from collections.abc import Sequence
from concurrent import futures
import logging
from logging.handlers import QueueHandler
import multiprocessing
from queue import Queue  # needed for mypy
import time
from typing import TypeAlias

from tqdm.contrib.logging import tqdm_logging_redirect


logger = logging.getLogger(__name__)


DataQueue: TypeAlias = Queue[logging.LogRecord | int]


def sleep(millis: int, log_queue: DataQueue) -> int:
    handler = QueueHandler(log_queue)
    root = logging.getLogger()
    root.handlers.clear()  # Need this otherwise will get double logging
    root.addHandler(handler)
    logger = logging.getLogger(
        f'{__name__}.{multiprocessing.current_process().name}'
    )

    sleeptime = millis / 1000
    logger.info(f'Sleeping for {sleeptime} seconds...')
    time.sleep(sleeptime)
    logger.info(f'Returning {millis}...')
    return millis


def executor_runner(
    args: Sequence[int],
    queue: DataQueue,
    as_completed: bool,
    workers: None | int,
) -> None:
    with futures.ProcessPoolExecutor(workers) as ex:
        fs = [ex.submit(sleep, x, queue) for x in args]
        for future in (futures.as_completed(fs) if as_completed else fs):
            queue.put(future.result())
        logger.debug('Finished as_completed')
    logger.debug('Close pool executor')


def main(n: int, as_completed: bool, workers: int | None = None) -> None:
    """
    If as_completed is True then will print out the results as they are
    completed: 1, 2, 3, 4

    If as_completed is False then will wait for all to finish and then print
    out all at once: 4, 3, 2, 1
    """

    if n < 1:
        raise ValueError('n must be > 0')

    logger.debug('Starting multiprocessing pool...')
    with multiprocessing.Manager() as m:
        queue: DataQueue = m.Queue(-1)
        args = list(range(n, 0, -1))

        # Have to use a process since forking and threading is unsafe; see
        # fork(2)
        executor_process = multiprocessing.Process(
            target=executor_runner,
            args=(args, queue, as_completed, workers)
        )

        executor_process.start()

        num = 0
        with tqdm_logging_redirect(total=n) as pbar:
            while num < n:
                r = queue.get()
                if isinstance(r, logging.LogRecord):
                    logger.handle(r)
                else:
                    logger.info(f'Returned: {r}')
                    num += 1
                    pbar.update(1)

        logger.debug('Joining...')
        executor_process.join()
        logger.debug('Joined')
    logger.debug('Closed manager')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('n', nargs='?', type=int, default=100)
    parser.add_argument('-j', '--workers', type=int)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    logging.basicConfig(level=logging.DEBUG)
    main(args.n, False, workers=args.workers)
    main(args.n, True, workers=args.workers)
