#!/usr/bin/env python3
"""Fetch and unpack arXiv source for source-assisted paper reading."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


ARXIV_RE = re.compile(r"((?:[a-z-]+(?:\.[A-Z]{2})?/\d{7})|(?:\d{4}\.\d{4,5}))(?:v\d+)?", re.IGNORECASE)


def normalize_arxiv_id(value: str) -> str | None:
    parsed = urllib.parse.urlparse(value)
    text = parsed.path if parsed.scheme else value
    match = ARXIV_RE.search(text) or ARXIV_RE.search(value)
    if not match:
        return None
    return re.sub(r"v\d+$", "", match.group(1), flags=re.IGNORECASE)


def safe_path(base: Path, name: str) -> Path:
    target = (base / name).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError(f"unsafe archive member path: {name}")
    return target


def unpack_archive(archive: Path, dest: Path, arxiv_id: str) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []

    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                target = safe_path(dest, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tf.extractfile(member)
                if source is None:
                    continue
                target.write_bytes(source.read())
                extracted.append(str(target))
        kind = "tar"
    elif zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                target = safe_path(dest, member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))
                extracted.append(str(target))
        kind = "zip"
    else:
        try:
            text = gzip.decompress(archive.read_bytes())
            target = dest / f"{arxiv_id.replace('/', '-')}.tex"
            target.write_bytes(text)
            extracted.append(str(target))
            kind = "gzip-tex"
        except OSError:
            target = dest / archive.name
            shutil.copy2(archive, target)
            extracted.append(str(target))
            kind = "raw"

    tex_files = [path for path in extracted if path.lower().endswith(".tex")]
    return {"kind": kind, "files": extracted, "tex_files": tex_files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="arXiv URL or ID.")
    parser.add_argument("--out-dir", required=True, help="Directory where source files should be unpacked.")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--strict", action="store_true", help="Return non-zero on fetch or unpack failure.")
    args = parser.parse_args()

    arxiv_id = normalize_arxiv_id(args.source)
    if not arxiv_id:
        result = {"ok": False, "source_available": False, "error": "could not parse arXiv ID"}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if args.strict else 0

    out_dir = Path(args.out_dir).expanduser() / arxiv_id.replace("/", "-")
    url = f"https://arxiv.org/e-print/{arxiv_id}"

    try:
        with tempfile.NamedTemporaryFile(prefix="arxiv-source-", delete=False) as tmp:
            with urllib.request.urlopen(url, timeout=args.timeout) as response:
                tmp.write(response.read())
            archive = Path(tmp.name)
        unpacked = unpack_archive(archive, out_dir, arxiv_id)
        result = {
            "ok": True,
            "source_available": True,
            "arxiv_id": arxiv_id,
            "source_url": url,
            "out_dir": str(out_dir),
            **unpacked,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "source_available": False,
            "arxiv_id": arxiv_id,
            "source_url": url,
            "out_dir": str(out_dir),
            "error": str(exc),
        }
    finally:
        try:
            archive.unlink()  # type: ignore[name-defined]
        except Exception:
            pass

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
