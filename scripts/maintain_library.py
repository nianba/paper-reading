#!/usr/bin/env python3
"""Maintain a small Obsidian-style paper vault idempotently."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def load_metadata(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_layout(vault: Path) -> dict[str, Path]:
    paths = {
        "notes": vault / "papers" / "notes",
        "metadata": vault / "papers" / "metadata",
        "pdfs": vault / "papers" / "pdfs",
        "assets": vault / "papers" / "assets",
        "navigation": vault / "papers" / "navigation",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def display_parts(metadata: dict) -> list[str]:
    parts = [str(metadata.get("year") or "unknown")]
    venue = metadata.get("venue")
    if venue and str(venue).lower() != "unknown":
        parts.append(str(venue))
    status = metadata.get("status")
    if status:
        parts.append(str(status))
    return parts


def render_entry(metadata: dict, note_slug: str) -> str:
    title = metadata.get("display_title") or metadata.get("title") or note_slug
    dedupe = metadata.get("dedupe_key") or f"local:{note_slug}"
    suffix = " · ".join(display_parts(metadata))
    visible = f"[[papers/notes/{note_slug}|{title}]]"
    if suffix:
        visible = f"{visible} · {suffix}"
    return f"- {visible} <!-- dedupe: {dedupe} -->"


def upsert_marked_entry(path: Path, heading: str, entry: str, dedupe_key: str) -> None:
    marker = f"<!-- dedupe: {dedupe_key} -->"
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [f"# {heading}", ""]

    replaced = False
    new_lines = []
    for line in lines:
        if marker in line:
            if not replaced:
                new_lines.append(entry)
                replaced = True
            continue
        new_lines.append(line)

    if not replaced:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def copy_optional(source: str | None, dest: Path) -> str | None:
    if not source:
        return None
    src = Path(source).expanduser()
    if not src.exists():
        raise FileNotFoundError(str(src))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return str(dest)


def load_figures(path: str | None) -> list[dict]:
    if not path:
        return []
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "assets" in data:
            return list(data["assets"])
        if "figures" in data:
            return list(data["figures"])
    if isinstance(data, list):
        return data
    raise ValueError("figures JSON must be a list or object with assets/figures")


def copy_figures(figures: list[dict], asset_root: Path, slug: str) -> list[dict]:
    copied = []
    target_dir = asset_root / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(figures, start=1):
        path = item.get("path") or item.get("image")
        if not path:
            continue
        src = Path(path).expanduser()
        if not src.exists():
            continue
        label = slugify(item.get("label") or src.stem or f"figure-{index}")
        dest = target_dir / f"{label}{src.suffix or '.png'}"
        shutil.copy2(src, dest)
        copied.append({**item, "path": str(dest), "label": label})
    return copied


def figure_markdown(figures: list[dict], slug: str, dedupe_key: str) -> str:
    begin = f"<!-- figures: {dedupe_key} begin -->"
    end = f"<!-- figures: {dedupe_key} end -->"
    lines = [begin, "", "## 关键图", ""]
    for item in figures:
        path = Path(item["path"])
        caption = item.get("caption") or item.get("label") or path.stem
        lines.append(f"![{caption}](../assets/{slug}/{path.name})")
        lines.append("")
        lines.append(f"> {caption}")
        lines.append("")
    lines.append(end)
    return "\n".join(lines)


def replace_managed_block(note_path: Path, block: str, dedupe_key: str) -> None:
    text = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
    begin = f"<!-- figures: {dedupe_key} begin -->"
    end = f"<!-- figures: {dedupe_key} end -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(block, text)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    note_path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, help="paper-vault root.")
    parser.add_argument("--metadata", required=True, help="Metadata JSON path.")
    parser.add_argument("--note", help="Optional Markdown note to copy into vault.")
    parser.add_argument("--pdf", help="Optional PDF to copy into vault.")
    parser.add_argument("--figures", help="Optional figure assets/candidates JSON.")
    parser.add_argument("--insert-figures", action="store_true", help="Insert copied figures into the managed note block.")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    paths = ensure_layout(vault)
    metadata = load_metadata(Path(args.metadata).expanduser())
    slug = metadata.get("slug") or slugify(metadata.get("title") or "paper")
    dedupe = metadata.get("dedupe_key") or f"local:{slug}"
    metadata["slug"] = slug
    metadata["dedupe_key"] = dedupe

    metadata_dest = paths["metadata"] / f"{slug}.json"
    metadata_dest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    note_dest = paths["notes"] / f"{slug}.md"
    note_path = copy_optional(args.note, note_dest)
    if not note_path and note_dest.exists():
        note_path = str(note_dest)

    pdf_path = copy_optional(args.pdf or metadata.get("pdf_path"), paths["pdfs"] / f"{slug}.pdf")

    figures = load_figures(args.figures)
    copied_figures = copy_figures(figures, paths["assets"], slug)
    if args.insert_figures and copied_figures and note_path:
        replace_managed_block(Path(note_path), figure_markdown(copied_figures, slug, dedupe), dedupe)

    entry = render_entry(metadata, slug)
    upsert_marked_entry(paths["navigation"] / "Papers Index.md", "Papers Index", entry, dedupe)
    upsert_marked_entry(paths["navigation"] / "By Year.md", "Papers By Year", entry, dedupe)

    result = {
        "ok": True,
        "vault": str(vault),
        "metadata": str(metadata_dest),
        "note": note_path,
        "pdf": pdf_path,
        "figures": copied_figures,
        "index": str(paths["navigation"] / "Papers Index.md"),
        "navigation": [str(paths["navigation"] / "By Year.md")],
        "dedupe_key": dedupe,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
