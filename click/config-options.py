"""
Getting missing click command options from a config file

This example uses JSON for the config file.
"""

import json
from pathlib import Path

import click


DEFAULT_CONF_NAME = '.default.json'


class Config:
    def __init__(self):
        self.config = {}

    def __repr__(self):
        items = ", ".join(f"{key}={val}" for key, val in self.config.items())
        return f'{type(self).__name__}({items})'

    def load(self, ctx, param, file):
        default_path = Path.home() / DEFAULT_CONF_NAME
        if file:
            self.config = json.load(file)
        elif default_path.exists():
            with open(default_path, 'rb') as file:
                self.config = json.load(file)
        else:
            self.config = {}

    def default(self, section, field):
        def default_map():
            return (self.config or {}).get(section, {}).get(field)

        return default_map


config = Config()


@click.command()
@click.option(
    '--config',
    type=click.File('rb'),
    expose_value=False,
    callback=config.load,
    is_eager=True,
    help=f"""Path to config JSON file; loads ~/{DEFAULT_CONF_NAME} by default
    if it exists"""
)
@click.option(
    '--host',
    default=config.default('app', 'host'),
    required=True,
    help="Overrides 'app:host' field in config file"
)
@click.option(
    '--token',
    default=config.default('app', 'token'),
    required=True,
    help="Overrides 'app:token' field in config file"
)
@click.option(
    '--local-dir',
    default=config.default('app', 'local-dir'),
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Overrides 'app:local-dir' field in config file; must exist"
)
def cli(host, token, local_dir):
    """
    Prints options taken from a config file.

    The config file format is:

    \b
        {
            "app": {
                "host": "<hostname>",
                "token": "<API token>",
                "local-dir": "<local data dir>"
            }
        }

    Example usage:

    \b
        python3 config-options.py --config test.json
    """
    print(host, token, local_dir)


if __name__ == '__main__':
    cli()
