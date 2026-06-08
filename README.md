# paper-reading

Codex skill for reading, explaining, summarizing, and organizing academic papers.

The skill is optimized for Chinese Markdown notes, slow paper walkthroughs, robotics/VLA papers, figure-aware reading, arXiv/PDF source handling, and Obsidian-style paper vault maintenance.

## What This Skill Covers

- Build a reading map before deep explanation.
- Keep paper facts, verified results, inference, and engineering advice separate.
- Produce durable Markdown notes in Simplified Chinese by default.
- Use paper figures conservatively, prioritizing framework diagrams, architecture diagrams, and key result figures.
- Maintain paper vault notes, metadata, PDFs, assets, and navigation files when requested.

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
