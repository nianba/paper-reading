#!/usr/bin/env python3
"""Extract paper metadata from an arXiv source or local PDF."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ARXIV_RE = re.compile(r"(?P<id>(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7})|(?:\d{4}\.\d{4,5}))(?:v\d+)?", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    text = parsed.path if parsed.scheme else value
    match = ARXIV_RE.search(text)
    if not match:
        match = ARXIV_RE.search(value)
    if not match:
        return None
    arxiv_id = match.group("id")
    return re.sub(r"v\d+$", "", arxiv_id, flags=re.IGNORECASE)


def slugify(value: str, fallback: str = "paper") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:80].strip("-") or fallback


def run_text_command(args: list[str]) -> str:
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True).stdout
    except OSError:
        return ""


def first_page_text(pdf: Path) -> str:
    if not shutil.which("pdftotext"):
        return ""
    return run_text_command(["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"])


def pdf_info(pdf: Path) -> dict:
    if not shutil.which("pdfinfo"):
        return {}
    output = run_text_command(["pdfinfo", str(pdf)])
    info = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip().lower().replace(" ", "_")] = value.strip()
    return info


def infer_title_from_text(text: str, fallback: str) -> str:
    candidates = []
    for line in text.splitlines()[:40]:
        cleaned = " ".join(line.strip().split())
        if 12 <= len(cleaned) <= 180 and not DOI_RE.search(cleaned):
            if not cleaned.lower().startswith(("abstract", "arxiv", "doi", "http")):
                candidates.append(cleaned)
    return candidates[0] if candidates else fallback


def fetch_arxiv_metadata(arxiv_id: str, timeout: float) -> tuple[dict, list[str]]:
    warnings = []
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:
        return {}, [f"arXiv metadata fetch failed: {exc}"]

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return {}, [f"arXiv metadata parse failed: {exc}"]

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return {}, ["arXiv metadata response did not include an entry"]

    def text(name: str) -> str | None:
        node = entry.find(f"atom:{name}", ns)
        return " ".join(node.text.split()) if node is not None and node.text else None

    authors = []
    for author in entry.findall("atom:author", ns):
        name = author.find("atom:name", ns)
        if name is not None and name.text:
            authors.append(" ".join(name.text.split()))

    published = text("published")
    year = published[:4] if published else None
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    for link in entry.findall("atom:link", ns):
        if link.attrib.get("title") == "pdf" and link.attrib.get("href"):
            pdf_url = link.attrib["href"]

    return {
        "title": text("title"),
        "authors": authors,
        "year": year,
        "abstract": text("summary"),
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "source_url": f"https://arxiv.org/abs/{arxiv_id}",
    }, warnings


def download_file(url: str, dest: Path, timeout: float) -> str | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            dest.write_bytes(response.read())
        return None
    except Exception as exc:
        return str(exc)


def metadata_from_local_pdf(pdf: Path) -> tuple[dict, list[str]]:
    warnings = []
    info = pdf_info(pdf)
    text = first_page_text(pdf)
    title = info.get("title") or infer_title_from_text(text, pdf.stem)
    arxiv_id = normalize_arxiv_id(text) or normalize_arxiv_id(pdf.name)
    doi_match = DOI_RE.search(text)
    year_match = YEAR_RE.search(text) or YEAR_RE.search(info.get("creationdate", ""))
    if not year_match:
        try:
            year = str(time.localtime(pdf.stat().st_mtime).tm_year)
        except OSError:
            year = None
    else:
        year = year_match.group(1)
    if not text:
        warnings.append("pdftotext unavailable or returned no first-page text")

    return {
        "title": title,
        "authors": [],
        "year": year,
        "pdf_producer": info.get("producer") or None,
        "arxiv_id": arxiv_id,
        "doi": doi_match.group(0) if doi_match else None,
        "pdf_path": str(pdf),
    }, warnings


def dedupe_key(metadata: dict) -> str:
    if metadata.get("arxiv_id"):
        return f"arxiv:{metadata['arxiv_id']}"
    if metadata.get("doi"):
        return f"doi:{metadata['doi'].lower()}"
    if metadata.get("title") and metadata.get("year"):
        return f"title-year:{slugify(metadata['title'])}:{metadata['year']}"
    return f"local:{slugify(metadata.get('title') or metadata.get('pdf_path') or 'paper')}"


def enrich_metadata(metadata: dict, source: str) -> dict:
    metadata = {key: value for key, value in metadata.items() if value not in ("", [], None)}
    title = metadata.get("title") or Path(source).stem
    arxiv_id = metadata.get("arxiv_id")
    slug_seed = f"{arxiv_id}-{title}" if arxiv_id else title
    metadata.setdefault("title", title)
    metadata["slug"] = slugify(slug_seed)
    metadata["dedupe_key"] = dedupe_key(metadata)
    metadata.setdefault("status", "unread")
    metadata.setdefault("tags", [])
    metadata["ingested_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return metadata


def write_metadata(metadata: dict, args: argparse.Namespace) -> Path | None:
    if args.metadata_out:
        path = Path(args.metadata_out).expanduser()
    elif args.vault:
        path = Path(args.vault).expanduser() / "papers" / "metadata" / f"{metadata['slug']}.json"
    elif args.out_dir:
        path = Path(args.out_dir).expanduser() / f"{metadata['slug']}.json"
    else:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="arXiv URL/ID, PDF URL, or local PDF path.")
    parser.add_argument("--vault", help="Optional paper-vault root.")
    parser.add_argument("--out-dir", help="Directory for standalone metadata output.")
    parser.add_argument("--metadata-out", help="Exact metadata JSON output path.")
    parser.add_argument("--download-pdf", action="store_true", help="Download arXiv/PDF URL into vault or out-dir.")
    parser.add_argument("--copy-pdf", action="store_true", help="Copy a local PDF into vault or out-dir.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Network timeout in seconds.")
    args = parser.parse_args()

    source = args.source
    source_path = Path(source).expanduser()
    warnings: list[str] = []
    metadata: dict
    downloaded_pdf: str | None = None

    arxiv_id = normalize_arxiv_id(source)
    is_pdf_url = source.startswith(("http://", "https://")) and urllib.parse.urlparse(source).path.lower().endswith(".pdf")

    if source_path.exists() and source_path.is_file():
        metadata, warnings = metadata_from_local_pdf(source_path)
    elif arxiv_id:
        metadata, warnings = fetch_arxiv_metadata(arxiv_id, args.timeout)
        if not metadata:
            metadata = {"arxiv_id": arxiv_id, "title": arxiv_id, "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"}
    elif is_pdf_url:
        metadata = {"title": Path(urllib.parse.urlparse(source).path).stem, "pdf_url": source}
    else:
        metadata = {"title": source}
        warnings.append("source was not recognized as a local PDF, arXiv source, or PDF URL")

    metadata = enrich_metadata(metadata, source)

    pdf_target_root = None
    if args.vault:
        pdf_target_root = Path(args.vault).expanduser() / "papers" / "pdfs"
    elif args.out_dir:
        pdf_target_root = Path(args.out_dir).expanduser()

    if args.download_pdf and metadata.get("pdf_url") and pdf_target_root:
        target = pdf_target_root / f"{metadata['slug']}.pdf"
        error = download_file(metadata["pdf_url"], target, args.timeout)
        if error:
            warnings.append(f"PDF download failed: {error}")
        else:
            downloaded_pdf = str(target)
            metadata["pdf_path"] = downloaded_pdf

    if args.copy_pdf and source_path.exists() and pdf_target_root:
        target = pdf_target_root / f"{metadata['slug']}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        metadata["pdf_path"] = str(target)

    metadata_path = write_metadata(metadata, args)
    result = {"metadata": metadata, "metadata_path": str(metadata_path) if metadata_path else None, "warnings": warnings}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
