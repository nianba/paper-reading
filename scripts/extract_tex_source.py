#!/usr/bin/env python3
"""Fetch and unpack arXiv source for source-assisted paper reading."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


ARXIV_RE = re.compile(r"((?:[a-z-]+(?:\.[A-Z]{2})?/\d{7})|(?:\d{4}\.\d{4,5}))(?:v\d+)?", re.IGNORECASE)
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\s*\[(?P<options>[^\]]*)\])?\s*\{(?P<reference>[^}]+)\}")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
MARKDOWN_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}


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


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "figure"


def read_text_lossy(path: Path) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def collect_image_files(files: list[str]) -> list[str]:
    return sorted({path for path in files if Path(path).suffix.lower() in IMAGE_EXTENSIONS})


def path_key(path: Path | str) -> str:
    return str(Path(path).expanduser().resolve()).lower()


def normalize_graphics_reference(reference: str) -> str:
    return reference.strip().strip("\"'")


def match_graphics_reference(reference: str, tex_file: Path, root: Path, image_files: list[str]) -> list[str]:
    reference = normalize_graphics_reference(reference)
    if not reference or "\\" in reference:
        return []

    image_lookup = {path_key(path): path for path in image_files}
    ref_path = Path(reference)
    search_roots = [tex_file.parent, root]
    candidates: list[Path] = []

    for search_root in search_roots:
        base = search_root / ref_path
        if ref_path.suffix:
            candidates.append(base)
        else:
            candidates.extend(Path(f"{base}{extension}") for extension in sorted(IMAGE_EXTENSIONS))

    matches: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = path_key(candidate)
        if key in image_lookup and key not in seen:
            matches.append(image_lookup[key])
            seen.add(key)
    return matches


def extract_graphics_refs(tex_files: list[str], image_files: list[str], root: Path) -> list[dict]:
    refs = []
    for tex_file_text in sorted(tex_files):
        tex_file = Path(tex_file_text)
        text = read_text_lossy(tex_file)
        for match in GRAPHICS_RE.finditer(text):
            reference = normalize_graphics_reference(match.group("reference"))
            refs.append(
                {
                    "tex_file": str(tex_file),
                    "reference": reference,
                    "options": match.group("options"),
                    "matches": match_graphics_reference(reference, tex_file, root, image_files),
                }
            )
    return refs


def convert_pdf_image(source: Path, target: Path) -> tuple[bool, str | None]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return False, "pdftoppm is not available for source PDF image conversion"

    prefix = target.with_suffix("")
    result = run([pdftoppm, "-png", "-singlefile", "-f", "1", "-l", "1", str(source), str(prefix)])
    output = prefix.with_suffix(".png")
    if result.returncode == 0 and output.exists():
        return True, None
    return False, result.stderr.strip() or "pdftoppm failed to convert source PDF image"


def convert_eps_image(source: Path, target: Path) -> tuple[bool, str | None]:
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool:
        return False, "ImageMagick is not available for source EPS image conversion"

    result = run([tool, str(source), str(target)])
    if result.returncode == 0 and target.exists():
        return True, None
    return False, result.stderr.strip() or "ImageMagick failed to convert source EPS image"


def convert_source_images(image_files: list[str], out_dir: Path) -> tuple[list[dict], list[str]]:
    converted = []
    diagnostics = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for image_file in sorted(image_files):
        source = Path(image_file).expanduser()
        suffix = source.suffix.lower()
        item = {
            "original_path": str(source),
            "path": str(source),
            "format": suffix,
            "converted": False,
        }

        if suffix in MARKDOWN_IMAGE_EXTENSIONS:
            converted.append(item)
            continue

        target = out_dir / f"{slugify(source.stem)}.png"
        if suffix == ".pdf":
            ok, warning = convert_pdf_image(source, target)
        elif suffix == ".eps":
            ok, warning = convert_eps_image(source, target)
        else:
            ok, warning = False, f"source image format {suffix or '<none>'} is not convertible by this script"

        if ok:
            item["path"] = str(target)
            item["converted"] = True
        elif warning:
            diagnostics.append(f"{source}: {warning}")
        converted.append(item)
    return converted, diagnostics


def build_source_image_assets(image_files: list[str], graphics_refs: list[dict], converted_images: list[dict] | None = None) -> list[dict]:
    refs_by_path: dict[str, list[dict]] = {}
    for ref in graphics_refs:
        for match in ref.get("matches", []):
            refs_by_path.setdefault(path_key(match), []).append(ref)

    converted_by_original = {
        path_key(item["original_path"]): item
        for item in converted_images or []
    }

    assets = []
    for image_file in sorted(image_files):
        source_path = Path(image_file)
        refs = refs_by_path.get(path_key(image_file), [])
        converted = converted_by_original.get(path_key(image_file))
        path = converted["path"] if converted else str(source_path)
        label_seed = refs[0]["reference"] if refs else source_path.stem
        asset = {
            "path": path,
            "original_path": str(source_path),
            "label": slugify(Path(label_seed).stem),
            "caption": refs[0]["reference"] if refs else source_path.name,
            "source": "tex-source",
            "format": source_path.suffix.lower(),
            "referenced_in_tex": bool(refs),
            "tex_refs": [ref["reference"] for ref in refs],
            "tex_files": sorted({ref["tex_file"] for ref in refs}),
        }
        if converted and converted.get("converted"):
            asset["converted_from"] = converted["original_path"]
        assets.append(asset)
    return assets


def unpack_archive(archive: Path, dest: Path, arxiv_id: str, convert_images: bool = False) -> dict:
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

    tex_files = sorted({path for path in extracted if path.lower().endswith(".tex")})
    image_files = collect_image_files(extracted)
    graphics_refs = extract_graphics_refs(tex_files, image_files, dest)
    converted_images, conversion_diagnostics = (
        convert_source_images(image_files, dest / "_converted_images") if convert_images else ([], [])
    )
    source_image_assets = build_source_image_assets(image_files, graphics_refs, converted_images)
    return {
        "kind": kind,
        "files": extracted,
        "tex_files": tex_files,
        "image_files": image_files,
        "graphics_refs": graphics_refs,
        "converted_images": converted_images,
        "source_image_assets": source_image_assets,
        "diagnostics": conversion_diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="arXiv URL or ID.")
    parser.add_argument("--out-dir", required=True, help="Directory where source files should be unpacked.")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--convert-images", action="store_true", help="Convert source PDF/EPS figures to PNG when possible.")
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
        unpacked = unpack_archive(archive, out_dir, arxiv_id, convert_images=args.convert_images)
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
