# paper-reading

Codex skill for reading, explaining, summarizing, and organizing academic papers.

The skill is optimized for Chinese Markdown notes, slow paper walkthroughs, robotics/VLA papers, figure-aware reading, arXiv/PDF source handling, and Obsidian-style paper vault maintenance.

## What This Skill Covers

- Build a reading map before deep explanation.
- Keep paper facts, verified results, inference, and engineering advice separate.
- Produce durable Markdown notes in Simplified Chinese by default.
- Use paper figures conservatively, prioritizing framework diagrams, architecture diagrams, and key result figures.
- Maintain paper vault notes, metadata, PDFs, assets, and navigation files when requested.

## Usage

### In Codex

Use this skill when the task is about understanding or organizing an academic paper. Reference it directly when you want to force the workflow:

```text
Use $paper-reading to read this paper slowly: https://arxiv.org/abs/<arxiv-id>
```

Useful prompt shapes:

```text
Use $paper-reading to read this local PDF slowly. Start with a reading map, then explain each section in Chinese.
```

```text
Use $paper-reading to turn this paper into a detailed Chinese Markdown note with the key framework and result figures placed near the relevant explanations.
```

```text
Use $paper-reading to maintain my paper vault for this paper: extract metadata, save the note, keep the PDF/assets, and update navigation.
```

Do not use this skill for pure presentation formatting when the paper content is already understood. Keep Markdown as the canonical output and apply presentation enhancement only as a separate optional step.

### Running Helper Scripts

Run scripts from the repository root. Replace the placeholder variables with real local paths or paper IDs before running commands.

```bash
PAPER=/absolute/path/to/paper.pdf
WORK=/absolute/path/to/work-dir
VAULT=/absolute/path/to/paper-vault
ARXIV_ID=replace-with-arxiv-id
```

Check local readiness:

```bash
python3 scripts/doctor.py --vault "$VAULT"
```

Extract metadata from an arXiv URL/ID, PDF URL, or local PDF:

```bash
python3 scripts/ingest_paper.py "$PAPER" --out-dir "$WORK"
```

Fetch arXiv source and prepare source image assets when available:

```bash
python3 scripts/extract_tex_source.py "$ARXIV_ID" --out-dir "$WORK/source" --convert-images
```

Generate conservative figure candidates from a local PDF:

```bash
python3 scripts/extract_figures.py "$PAPER" --out-dir "$WORK/figures" --pages 1-5
```

Maintain a paper vault after metadata and note files are ready:

```bash
python3 scripts/maintain_library.py \
  --vault "$VAULT" \
  --metadata "$WORK/metadata.json" \
  --note "$WORK/note.md" \
  --pdf "$PAPER"
```

Treat extracted figures as candidates. Review them before inserting into final notes or use a manual crop manifest when automatic extraction is weak.

## Repository Layout

```text
.
|-- SKILL.md                  # Skill trigger metadata and core workflow
|-- agents/openai.yaml        # UI-facing skill metadata
|-- references/               # Optional guidance loaded only when needed
|-- scripts/                  # Helper scripts for metadata, figures, TeX source, and vault maintenance
`-- tests/test_scripts.py     # Focused regression tests for helper scripts
```

## Helper Scripts

- `scripts/doctor.py` checks local tooling, vault writability, and optional network readiness.
- `scripts/ingest_paper.py` extracts or normalizes paper metadata.
- `scripts/extract_tex_source.py` fetches and indexes arXiv source assets when available.
- `scripts/extract_figures.py` generates candidate figure assets from PDFs.
- `scripts/maintain_library.py` updates vault notes, metadata, PDFs, assets, index, and navigation files.

## Validation

Run the focused test suite from the repository root:

```bash
python3 -m unittest tests/test_scripts.py
```

Run the local readiness check:

```bash
python3 scripts/doctor.py
```

## Maintenance Notes

- Keep `SKILL.md` concise and focused on agent instructions.
- Put detailed style guidance or failure-mode notes under `references/`.
- Prefer deterministic helper scripts for fragile or repeatable operations.
- Keep Markdown as the canonical note format; presentation enhancement should remain optional and capability-driven.
