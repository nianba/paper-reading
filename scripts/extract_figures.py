#!/usr/bin/env python3
"""Render PDF pages and produce conservative figure candidates."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


FIGURE_RE = re.compile(r"\b(fig(?:ure)?\.?\s*\d+[:.]?.*)", re.IGNORECASE)


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def extract_caption_candidates(pdf: Path) -> list[dict]:
    if not shutil.which("pdftotext"):
        return []
    result = run(["pdftotext", str(pdf), "-"])
    if result.returncode != 0:
        return []
    captions = []
    for line in result.stdout.splitlines():
        cleaned = " ".join(line.split())
        match = FIGURE_RE.search(cleaned)
        if match:
            captions.append({"caption": match.group(1), "source": "pdftotext"})
    return captions


def render_pages(pdf: Path, out_dir: Path, slug: str, max_pages: int, dpi: int) -> tuple[list[Path], list[str]]:
    diagnostics = []
    if not shutil.which("pdftoppm"):
        return [], ["pdftoppm is not available; page rendering skipped"]

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / f"{slug}-page"
    args = ["pdftoppm", "-png", "-r", str(dpi), "-f", "1", "-l", str(max_pages), str(pdf), str(prefix)]
    result = run(args)
    if result.returncode != 0:
        diagnostics.append(result.stderr.strip() or "pdftoppm failed")
        return [], diagnostics
    pages = sorted(out_dir.glob(f"{slug}-page-*.png"))
    return pages, diagnostics


def load_manifest(path: str | None) -> list[dict]:
    if not path:
        return []
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("figures", []))
    if isinstance(data, list):
        return data
    raise ValueError("manifest must be a list or an object with a figures list")


def crop_with_available_tool(source: Path, target: Path, bbox: dict) -> tuple[bool, str | None]:
    x = int(bbox["x"])
    y = int(bbox["y"])
    width = int(bbox["width"])
    height = int(bbox["height"])
    target.parent.mkdir(parents=True, exist_ok=True)

    magick = shutil.which("magick")
    convert = shutil.which("convert")
    if magick:
        result = run([magick, str(source), "-crop", f"{width}x{height}+{x}+{y}", str(target)])
    elif convert:
        result = run([convert, str(source), "-crop", f"{width}x{height}+{x}+{y}", str(target)])
    else:
        shutil.copy2(source, target)
        return False, "no crop tool available; copied full rendered page"

    if result.returncode != 0:
        shutil.copy2(source, target)
        return False, result.stderr.strip() or "crop command failed; copied full rendered page"
    return True, None


def apply_manual_manifest(figures: list[dict], pages: list[Path], out_dir: Path, slug: str) -> tuple[list[dict], list[str]]:
    diagnostics = []
    assets = []
    page_by_number = {}
    for page in pages:
        match = re.search(r"-(\d+)\.png$", page.name)
        if match:
            page_by_number[int(match.group(1))] = page

    for index, item in enumerate(figures, start=1):
        page_number = int(item.get("page", 1))
        source = page_by_number.get(page_number)
        label = slugify(item.get("label") or f"figure-{index}")
        target = out_dir / f"{slug}-{label}.png"
        if source is None:
            diagnostics.append(f"manual figure {label}: rendered page {page_number} not found")
            continue
        bbox = item.get("bbox")
        if bbox:
            crop_applied, warning = crop_with_available_tool(source, target, bbox)
        else:
            shutil.copy2(source, target)
            crop_applied, warning = False, "no bbox provided; copied full rendered page"
        if warning:
            diagnostics.append(f"manual figure {label}: {warning}")
        assets.append({
            "label": label,
            "page": page_number,
            "path": str(target),
            "caption": item.get("caption"),
            "crop_applied": crop_applied,
        })
    return assets, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Local PDF path.")
    parser.add_argument("--out-dir", required=True, help="Output directory for rendered pages/assets.")
    parser.add_argument("--slug", help="Paper slug; defaults to PDF stem.")
    parser.add_argument("--max-pages", type=int, default=6, help="Number of pages to render for candidates.")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--manifest", help="Manual crop manifest JSON.")
    parser.add_argument("--diagnostics-out", help="Diagnostics JSON path.")
    parser.add_argument("--candidates-out", help="Candidates JSON path.")
    args = parser.parse_args()

    pdf = Path(args.pdf).expanduser()
    slug = slugify(args.slug or pdf.stem)
    out_dir = Path(args.out_dir).expanduser()
    page_dir = out_dir / "pages"
    asset_dir = out_dir / "assets"

    diagnostics = []
    if not pdf.exists():
        diagnostics.append(f"PDF not found: {pdf}")
        result = {"ok": False, "diagnostics": diagnostics, "candidates": [], "assets": []}
    else:
        captions = extract_caption_candidates(pdf)
        pages, render_diagnostics = render_pages(pdf, page_dir, slug, args.max_pages, args.dpi)
        diagnostics.extend(render_diagnostics)
        candidates = []
        for index, page in enumerate(pages, start=1):
            caption = captions[index - 1]["caption"] if index - 1 < len(captions) else None
            candidates.append({
                "page": index,
                "image": str(page),
                "caption": caption,
                "reason": "rendered_page_with_possible_caption" if caption else "rendered_page_candidate",
            })
        manifest = load_manifest(args.manifest)
        assets, manifest_diagnostics = apply_manual_manifest(manifest, pages, asset_dir, slug)
        diagnostics.extend(manifest_diagnostics)
        result = {
            "ok": True,
            "pdf": str(pdf),
            "slug": slug,
            "diagnostics": diagnostics,
            "candidates": candidates,
            "assets": assets,
            "note": "Automatic output is candidate generation; review important figures before final insertion.",
        }

    if args.diagnostics_out:
        path = Path(args.diagnostics_out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"diagnostics": result["diagnostics"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.candidates_out:
        path = Path(args.candidates_out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
