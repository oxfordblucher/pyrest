import logging

import click
from flask import current_app
from flask.cli import with_appcontext

from scryapi.sync import run_sync
from scryapi.sync.download import SyncError

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
@click.option(
    "--allow-removals",
    is_flag=True,
    help="Import even if it would remove an unusually large number of cards (and so "
    "remove them from decks).",
)
@with_appcontext
def sync_cards_command(file: str | None, force: bool, allow_removals: bool) -> None:
    """Download Scryfall Oracle bulk data and upsert it into the catalogue.

    Cards Scryfall no longer lists are hidden and removed from decks; their owners are
    notified.
    """
    try:
        result = run_sync(file=file, force=force, allow_removals=allow_removals)
    except SyncError as e:
        raise click.ClickException(str(e)) from e
    imported = result.imported
    if imported is None:
        click.echo("Card data is already up to date.")
        return
    click.echo(f"Imported {imported.imported} cards ({imported.skipped} skipped).")
    if imported.dropped or imported.decks_changed:
        click.echo(
            f"{imported.dropped} cards were removed by Scryfall; "
            f"{imported.decks_changed} decks changed and their owners were notified."
        )


@click.command("run-scheduler")
@click.option(
    "--interval",
    default=WEEK_SECONDS,
    show_default=True,
    help="Seconds between sync attempts.",
)
@with_appcontext
def run_scheduler_command(interval: int) -> None:
    """Run the card sync now and then every INTERVAL seconds, in this one process.

    Prefer an external cron calling `flask sync-cards` in production (docs/TDD.md §7).
    """
    from scryapi.sync.scheduler import run_forever

    logging.basicConfig(level=logging.INFO)
    run_forever(current_app._get_current_object(), interval)  # type: ignore[attr-defined]
