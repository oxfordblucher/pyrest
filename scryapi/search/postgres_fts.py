from scryapi.extensions import db

# cards.search_vector (generated tsvector over oracle_text, GIN-indexed) and pg_trgm
# indexes on name/type_line are created by the baseline migration.


class PostgresFtsBackend:
    def apply_text_filter(self, stmt, text):
        if not text.strip():
            return stmt
        # websearch_to_tsquery accepts any input without raising.
        return stmt.where(
            db.text("cards.search_vector @@ websearch_to_tsquery('english', :q)").bindparams(q=text)
        )

    def rebuild(self):
        # search_vector is a generated column; nothing to do.
        pass
