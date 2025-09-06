#!/usr/bin/env python3

import concurrent.futures
import csv
import fnmatch
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sys
from collections.abc import Callable, Iterable, Iterator
from typing import IO, NamedTuple

import click
import tqdm


class HashAlgorithmOption(click.ParamType):
    name = "hash algorithm"

    def convert(
        self,
        value: str,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> str:
        if value not in hashlib.algorithms_available:
            self.fail(f"unsupported hash algorithm '{value}'", param, ctx)
        return value


@click.command()
@click.argument(
    "paths",
    required=True,
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--jobs", "-j", type=click.IntRange(min=1))
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="""Do not print any output and exit with non-zero code if there are no
    identical files or if --match/-m is passed and there are no matches.""",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    help="Output format.",
    default="txt",
    type=click.Choice(("txt", "json", "csv")),
    show_default=True,
)
@click.option(
    "--hash",
    "-h",
    "hash_algorithm",
    default="md5",
    show_default=True,
    help="Hash algorithm; md5, sha1, sha256 etc.",
    type=HashAlgorithmOption(),
)
@click.option(
    "--match",
    "-m",
    "match_digests",
    multiple=True,
    help="""Only output files whose hash matches the digest. Exits with
    non-zero code if no files found. Can be repeated.""",
)
@click.option("--progress/--no-progress", "show_progress", default=True)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="""Recurse into provided directories.""",
)
@click.option(
    "--glob",
    "-g",
    help="""Only process files with name matching globs. Prepend with ! to negate.
    Case-sensitive unless --glob-case-insensitive/-i passed.""",
)
@click.option("--glob-case-insensitive", "-i", is_flag=True)
def main(
    paths: list[Path],
    jobs: int | None,
    quiet: bool,
    output_format: str,
    hash_algorithm: str,
    match_digests: list[str],
    show_progress: bool,
    recursive: bool,
    glob: str | None,
    glob_case_insensitive: bool,
) -> None:
    """List files with the same checksum."""
    if quiet:
        show_progress = False

    with concurrent.futures.ProcessPoolExecutor(jobs) as pool:
        file_hashes = _file_hashes(
            pool,
            hash_algorithm,
            _collect_file_paths(paths, recursive, glob, glob_case_insensitive),
            show_progress,
        )

    if match_digests:
        to_match = set(match_digests)
        file_hashes = {
            digest: paths for digest, paths in file_hashes.items() if digest in to_match
        }
    else:
        file_hashes = {
            digest: paths for digest, paths in file_hashes.items() if len(paths) > 1
        }

    if quiet:
        sys.exit(0 if file_hashes else 1)

    if output_format == "txt":
        if match_digests:
            _echo_matched_digests(file_hashes)
        else:
            _echo_duplicate_files(file_hashes, hash_algorithm)
    elif output_format == "json":
        print(json.dumps(file_hashes, indent=2))
    elif output_format == "csv":
        _write_csv(file_hashes, hash_algorithm, sys.stdout)
    else:
        raise AssertionError(f"invalid format '{output_format}'")

    if match_digests and not file_hashes:
        sys.exit(1)


def _echo_matched_digests(file_hashes: dict[str, list[str]]) -> None:
    for digest, paths in file_hashes.items():
        for path in paths:
            msg = (
                click.style(digest, fg="red"),
                click.style(":", fg="green"),
                path,
            )
            click.echo("".join(msg))


def _echo_duplicate_files(identical: dict[str, list[str]], hash_algorithm: str) -> None:
    for digest, paths in identical.items():
        click.secho(
            f"{len(paths)} files with {hash_algorithm} hash '{digest}':",
            bold=True,
            fg="yellow",
        )
        click.echo("\n".join(paths))


def _write_csv(
    identical: dict[str, list[str]], hash_algorithm: str, f: IO[str]
) -> None:
    writer = csv.writer(f)
    writer.writerow((hash_algorithm, "path"))
    for digest, files in identical.items():
        for file in files:
            writer.writerow((digest, file))


class _HashResult(NamedTuple):
    path: str
    digest: str


class _Matcher:
    def __init__(self, glob: str, case_insensitive: bool):
        if glob.startswith("!"):
            glob = glob[1:]
            self.negate: bool = True
        else:
            self.negate = False

        self._name_matches: Callable[[str], bool]
        if case_insensitive:
            glob = glob.lower()
            self._name_matches = lambda name: fnmatch.fnmatch(name, glob)
        else:
            self._name_matches = partial(fnmatch.fnmatch, pat=glob)

    def __call__(self, filename: str) -> bool:
        if self._name_matches(filename):
            return not self.negate
        return self.negate


def _always_match(_: str) -> bool:
    return True


def _collect_file_paths(
    paths: Iterable[Path],
    recursive: bool,
    glob: str | None,
    glob_case_insensitive: bool,
) -> Iterator[Path]:
    if glob is None:
        filename_match = _always_match
    else:
        filename_match = _Matcher(glob, glob_case_insensitive)

    for path in set(paths):
        if path.is_file():
            if filename_match(path.name):
                yield path
        elif recursive and path.is_dir():
            for subdir, _, filenames in path.walk():
                file_paths = (subdir / name for name in filenames)
                if glob is None:
                    yield from file_paths
                else:
                    yield from (p for p in file_paths if filename_match(p.name))


def _compute_hash(
    path: str,
    hash_algorithm: str,
    blocksize: int = 0xFFFF,
) -> _HashResult:
    digest = hashlib.new(hash_algorithm)
    with open(path, "rb") as f:
        while True:
            data = f.read(blocksize)
            if not data:
                break
            digest.update(data)

    return _HashResult(path=path, digest=digest.hexdigest())


def _file_hashes(
    pool: concurrent.futures.ProcessPoolExecutor,
    hash_algorithm: str,
    paths: Iterable[Path],
    show_progress: bool,
) -> dict[str, list[str]]:
    futures: list[concurrent.futures.Future[_HashResult]] = [
        pool.submit(_compute_hash, str(path), hash_algorithm) for path in paths
    ]
    if not futures:
        click.secho("Warning: no files passed", bold=True, fg="yellow", err=True)
        return {}

    completed_futures = concurrent.futures.as_completed(futures)
    if show_progress:
        completed_futures = tqdm.tqdm(
            completed_futures,
            total=len(futures),
            desc=f"Computing {hash_algorithm} hashes",
            unit="files",
        )

    hashes: dict[str, list[str]] = {}
    for future in completed_futures:
        res = future.result()
        hashes.setdefault(res.digest, []).append(res.path)

    return {digest: sorted(paths) for digest, paths in hashes.items()}


if __name__ == "__main__":
    main()
