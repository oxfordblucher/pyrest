import logging
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BULK_INFO_URL = "https://api.scryfall.com/bulk-data/oracle_cards"
BULK_FILENAME = "oracle_cards.jsonl.gz"
TIMEOUT = (5, 60)  # (connect, read) seconds
CHUNK_SIZE = 64 * 1024


class SyncError(Exception):
    pass


@dataclass(frozen=True)
class BulkInfo:
    download_uri: str
    updated_at: str
    size: int | None


def _user_agent():
    try:
        return f"scryapi/{version('scryapi')}"
    except PackageNotFoundError:
        return "scryapi"


def make_session():
    """HTTP session following Scryfall's API guidelines (identifying headers, retries)."""
    session = requests.Session()
    session.headers.update(
        {"User-Agent": _user_agent(), "Accept": "application/json;q=0.9,*/*;q=0.8"}
    )
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_bulk_info(session):
    resp = session.get(BULK_INFO_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    try:
        return BulkInfo(
            download_uri=data["jsonl_download_uri"],
            updated_at=data["updated_at"],
            size=data.get("compressed_size"),
        )
    except KeyError as e:
        raise SyncError(f"Unexpected bulk-data response, missing {e}") from e


def download_bulk(session, info, dest_dir):
    """Download the bulk file to `dest_dir` atomically and return its path.

    The file is streamed to a `.part` file, its size checked against Scryfall's
    `compressed_size`, and only then moved over the previous download. A failed or
    truncated download leaves the previous file untouched.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / BULK_FILENAME
    part = dest_dir / (BULK_FILENAME + ".part")

    logger.info("Downloading %s", info.download_uri)
    try:
        with session.get(info.download_uri, stream=True, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            written = 0
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    written += len(chunk)
        if info.size is not None and written != info.size:
            raise SyncError(f"Truncated download: got {written} bytes, expected {info.size}")
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise

    logger.info("Downloaded %d bytes to %s", written, dest)
    return dest
