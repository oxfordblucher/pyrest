from flask import Blueprint

from scryapi.formats import FORMATS
from scryapi.schemas.deck import dump_format

formatsbp = Blueprint("formats", __name__, url_prefix="/api/formats")


@formatsbp.get("")
def list_formats():
    return {"results": [dump_format(f) for f in FORMATS.values()]}
