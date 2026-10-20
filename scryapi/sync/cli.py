import logging

import click
from flask import current_app
from flask.cli import with_appcontext

from scryapi.sync import run_sync

logger = logging.getLogger(__name__)

WEEK_SECONDS = 7 * 24 * 60 * 60


@click.command("sync-cards")
@click.option(
    "--file",
    "file",
    type=click.Path(exists=True, dir_okay=False),
    help="Import a local .jsonl, .jsonl.gz or .json file instead of downloading.",
)
@click.option("--force", is_flag=True, help="Import even if Scryfall's data is unchanged.")
@with_appcontext
def sync_cards_command(file, force):
    """Download Scryfall Oracle bulk data and upsert it into the catalogue."""
    result = run_sync(file=file, force=force)
    if result.status == "up_to_date":
        click.echo("Card data is already up to date.")
    else:
        click.echo(
            f"Imported {result.imported.imported} cards ({result.imported.skipped} skipped)."
        )


@click.command("run-scheduler")
@click.option(
    "--interval",
    default=WEEK_SECONDS,
    show_default=True,
    help="Seconds between sync attempts.",
)
@with_appcontext
def run_scheduler_command(interval):
    """Run the card sync now and then every INTERVAL seconds, in this one process.

    Prefer an external cron calling `flask sync-cards` in production (docs/TDD.md §7).
    """
    from scryapi.sync.scheduler import run_forever

    logging.basicConfig(level=logging.INFO)
    run_forever(current_app._get_current_object(), interval)
