from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{name}.py"), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class PaperReadingScriptTests(unittest.TestCase):
    def test_arxiv_id_normalization(self) -> None:
        ingest = load_module("ingest_paper")
        self.assertEqual(ingest.normalize_arxiv_id("https://arxiv.org/abs/2402.10329v2"), "2402.10329")
        self.assertEqual(ingest.normalize_arxiv_id("arXiv:cs/0301012v1"), "cs/0301012")
        self.assertIsNone(ingest.normalize_arxiv_id("not-a-paper"))

    def test_doctor_outputs_json(self) -> None:
        result = run_script("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("ok", payload)
        self.assertIn("local_ok", payload)
        self.assertIn("network_ok", payload)
        self.assertIn("tools", payload)

    def test_ingest_local_pdf_writes_metadata_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "Example Paper.pdf"
            pdf.write_text("placeholder PDF bytes for metadata fallback", encoding="utf-8")
            out_dir = root / "out"

            result = run_script("ingest_paper", str(pdf), "--out-dir", str(out_dir))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            metadata_path = Path(payload["metadata_path"])
            self.assertTrue(metadata_path.exists())
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["title"], "Example Paper")
            self.assertIn("dedupe_key", metadata)
            self.assertIn("slug", metadata)

    def test_maintain_library_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = {
                "title": "Example Paper",
                "year": "2026",
                "venue": "arXiv",
                "status": "reading",
                "slug": "example-paper",
                "dedupe_key": "arxiv:2601.00001",
            }
            metadata_path = root / "metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            note_path = root / "note.md"
            note_path.write_text("# Example Paper\n", encoding="utf-8")
            vault = root / "paper-vault"

            for _ in range(2):
                result = run_script(
                    "maintain_library",
                    "--vault",
                    str(vault),
                    "--metadata",
                    str(metadata_path),
                    "--note",
                    str(note_path),
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            index = vault / "papers" / "navigation" / "Papers Index.md"
            by_year = vault / "papers" / "navigation" / "By Year.md"
            self.assertEqual(index.read_text(encoding="utf-8").count("<!-- dedupe: arxiv:2601.00001 -->"), 1)
            self.assertEqual(by_year.read_text(encoding="utf-8").count("<!-- dedupe: arxiv:2601.00001 -->"), 1)
            self.assertTrue((vault / "papers" / "notes" / "example-paper.md").exists())
            self.assertTrue((vault / "papers" / "metadata" / "example-paper.json").exists())

    def test_manifest_figure_insertion_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = {
                "title": "Figure Paper",
                "year": "2026",
                "slug": "figure-paper",
                "dedupe_key": "arxiv:2601.00002",
            }
            metadata_path = root / "metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            note_path = root / "note.md"
            note_path.write_text("# Figure Paper\n", encoding="utf-8")
            image_path = root / "pipeline.png"
            image_path.write_bytes(b"fake-image")
            figures_path = root / "figures.json"
            figures_path.write_text(
                json.dumps({"assets": [{"path": str(image_path), "label": "pipeline", "caption": "Pipeline"}]}),
                encoding="utf-8",
            )
            vault = root / "paper-vault"

            for _ in range(2):
                result = run_script(
                    "maintain_library",
                    "--vault",
                    str(vault),
                    "--metadata",
                    str(metadata_path),
                    "--note",
                    str(note_path),
                    "--figures",
                    str(figures_path),
                    "--insert-figures",
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            note = (vault / "papers" / "notes" / "figure-paper.md").read_text(encoding="utf-8")
            self.assertEqual(note.count("<!-- figures: arxiv:2601.00002 begin -->"), 1)
            self.assertEqual(note.count("![Pipeline]"), 1)

    def test_extract_figures_missing_pdf_returns_json_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script("extract_figures", str(Path(tmp) / "missing.pdf"), "--out-dir", tmp)
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("diagnostics", payload)

    def test_extract_tex_bad_source_is_graceful_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script("extract_tex_source", "not-a-paper", "--out-dir", tmp)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["source_available"])


if __name__ == "__main__":
    unittest.main()
