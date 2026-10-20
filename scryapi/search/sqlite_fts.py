from scryapi.extensions import db
from scryapi.models import Card

# cards_fts (FTS5, external content over cards.oracle_text, porter stemming) is created by
# the baseline migration.


def build_fts_query(text):
    """Turn arbitrary user input into a valid FTS5 query.

    Each whitespace-separated term becomes a quoted string (internal quotes doubled), so
    FTS5 operators and syntax characters are matched literally and can never raise a
    syntax error. Terms are ANDed (FTS5's implicit operator).
    """
    return " ".join('"' + term.replace('"', '""') + '"' for term in text.split())


class SqliteFtsBackend:
    def apply_text_filter(self, stmt, text):
        query = build_fts_query(text)
        if not query:
            return stmt
        matching_ids = (
            db.text("SELECT rowid FROM cards_fts WHERE cards_fts MATCH :q")
            .bindparams(q=query)
            .columns(db.column("rowid", db.Integer))
        )
        return stmt.where(Card.id.in_(matching_ids))

    def rebuild(self):
        # cards_fts is an external-content table with no triggers: the sync importer is
        # the only writer to `cards`, so it rebuilds the index once per import.
        db.session.execute(db.text("INSERT INTO cards_fts(cards_fts) VALUES('rebuild')"))
