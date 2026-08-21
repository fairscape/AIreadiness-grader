"""Range-GET a remote file to a local path, capped at N bytes.

Used by the remote-schema-infer skill to sample tabular files (CSV/TSV) from
Dataverse / PhysioNet without downloading the entire dataset. If the server
honors HTTP Range, only the first ``max-bytes`` are transferred. If not, the
stream is read and truncated client-side.

For text formats (default), the trailing partial line is dropped after
truncation so schema-infer never sees a half-written row.

For binary formats like Parquet/HDF5 — where the schema lives in the
file footer — pass ``--no-trim-tail`` and ``--max-bytes 0`` (unlimited)
to download the full file. Range-truncating a parquet file makes the
footer magic bytes unreadable and ``schema infer`` will error out.

CLI:
    python -m aireadiness_wizard.remote_fetch <url> <out> [--max-bytes N] [--no-trim-tail]

``--max-bytes 0`` means no cap (download the whole file).

Exits 0 on success, prints a one-line JSON summary to stdout:
    {"path": "...", "bytes_written": N, "used_range": true|false,
     "status": 200|206, "truncated_tail_line": true|false}
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
CHUNK = 64 * 1024


def fetch_sample(url: str, out: Path, max_bytes: int, trim_tail: bool = True) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "fairscape-wizard/remote_fetch",
        "Accept": "*/*",
    }
    if max_bytes > 0:
        headers["Range"] = f"bytes=0-{max_bytes - 1}"
    req = urllib.request.Request(url, headers=headers)
    written = 0
    used_range = False
    status = None
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.status
            used_range = status == 206
            with out.open("wb") as f:
                while True:
                    if max_bytes > 0 and written >= max_bytes:
                        break
                    to_read = CHUNK if max_bytes <= 0 else min(CHUNK, max_bytes - written)
                    chunk = resp.read(to_read)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} fetching {url}: {e.reason}")
    except urllib.error.URLError as e:
        raise SystemExit(f"network error fetching {url}: {e.reason}")

    truncated_tail = _trim_incomplete_last_line(out) if trim_tail else False
    return {
        "path": str(out),
        "bytes_written": out.stat().st_size,
        "raw_bytes": written,
        "used_range": used_range,
        "status": status,
        "truncated_tail_line": truncated_tail,
    }


def _trim_incomplete_last_line(out: Path) -> bool:
    """If the file doesn't end in a newline, drop everything after the last \\n.

    Returns True if any bytes were dropped.
    """
    size = out.stat().st_size
    if size == 0:
        return False
    with out.open("rb") as f:
        f.seek(-1, 2)
        last = f.read(1)
    if last == b"\n":
        return False
    with out.open("rb") as f:
        data = f.read()
    idx = data.rfind(b"\n")
    if idx < 0:
        return False
    with out.open("wb") as f:
        f.write(data[: idx + 1])
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Range-GET a URL to disk, optionally capped at N bytes.")
    ap.add_argument("url")
    ap.add_argument("out", type=Path)
    ap.add_argument(
        "--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
        help="cap on bytes downloaded; 0 disables the cap (default: %(default)s)",
    )
    ap.add_argument(
        "--no-trim-tail", action="store_true",
        help="don't drop a trailing partial line — use for binary formats (parquet, hdf5)",
    )
    args = ap.parse_args(argv)
    summary = fetch_sample(args.url, args.out, args.max_bytes, trim_tail=not args.no_trim_tail)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
