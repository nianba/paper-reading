---
name: paper-reading
description: Use when reading, explaining, summarizing, or organizing academic papers from arXiv links, PDFs, local files, or an Obsidian paper vault; especially for Chinese Markdown notes, section-by-section walkthroughs, robotics/VLA papers, figure-aware notes, metadata extraction, TeX/source-assisted reading, and paper-library maintenance.
---

# Paper Reading

Use this skill to help the user actually understand a paper before turning it into durable notes.

Default to Simplified Chinese for explanations and note bodies. Keep English terms when they are standard technical names.

## Core Workflow

1. Identify the paper source: arXiv URL/ID, PDF URL, local PDF path, or an existing vault entry.
2. Extract or verify metadata: title, authors, year, venue, arXiv ID, DOI, code, dataset, and stable dedupe key when available.
3. Build a reading map before deep explanation: paper objective, section structure, key figures, method spine, experiment spine, and likely uncertainty points.
4. Explain in layers: problem background -> method structure -> inputs/outputs -> training supervision -> experiments -> limitations.
5. Treat figures conservatively: prioritize framework diagrams, model diagrams, and experimental result figures. Automatic extraction is only candidate generation.
6. Produce Markdown-first output: a stepwise explanation, a concise note, Markdown tables, or a vault note depending on the user's request.
7. If writing to a vault, maintain notes, metadata, PDFs, assets, and navigation/index pages, then verify the result with local evidence.

## Output Preferences

Do not force a fixed note template. Let the current paper and user goal decide the structure.

Stable preferences:

- Chinese prose by default; keep technical English terms when useful.
- Start with a reading map when the user says they want to read slowly, fully understand, or "慢慢来".
- When the user asks for review material, compress into Markdown tables or method-grouped short notes.
- Avoid empty macro headings such as "总览", "速览", "统一理解", or "总结" unless the user asks for them.
- Do not add heading numbers by default.
- For robotics, VLA, imitation learning, and post-training papers, preserve inputs, outputs, hardware assumptions, data sources, supervision labels, control frequencies, evaluation tasks, and failure boundaries.

Read `references/note-style.md` when producing a polished note, Markdown table, or recap artifact.

## Fact Boundaries

Keep these categories separate:

- What the paper explicitly claims.
- What the authors experimentally verify.
- What can be inferred from figures, equations, or released artifacts.
- What requires source code, official docs, or follow-up verification.
- Engineering recommendations beyond the paper.
- Related work or broader field context.

If the paper does not specify a training detail, model component, hardware assumption, or data source, say so directly instead of filling it in.

For foundation-model or post-training papers, separate upstream base-model facts from the current paper's post-training or adaptation facts.

## Source Handling

PDF is the canonical source. Use arXiv TeX/source only to improve section lookup, equation reading, figure naming, and citation tracing.

For two-column PDFs or noisy extracted text, prefer cross-checking:

1. PDF metadata and rendered pages.
2. Raw `pdftotext` output.
3. arXiv source if available.
4. Figure previews and captions.

Do not treat layout-extracted text as authoritative when section order is visibly wrong.

## Figure Handling

Use `scripts/extract_figures.py` only as a candidate generator. It may render pages and identify likely figure captions, but it should not be treated as final visual truth.

Prefer high-value figures:

- Overall framework or pipeline.
- Model architecture or data flow.
- Key training/evaluation setup.
- Main result or ablation table/plot.

When auto-cropping is weak, use diagnostics plus a reviewed manual crop manifest. Never block note creation only because figure extraction failed.

Read `references/failure-cases.md` before debugging figure, PDF extraction, vault, or index issues.

## Vault Workflow

When the user asks to archive or maintain a paper library, default vault layout is:

```text
paper-vault/
└── papers/
    ├── notes/
    ├── metadata/
    ├── pdfs/
    ├── assets/
    └── navigation/
```

Use scripts as helpers, not as user-facing manual steps:

- `scripts/doctor.py`: check local tools, vault writability, and optional network status.
- `scripts/ingest_paper.py`: extract metadata and write JSON.
- `scripts/extract_tex_source.py`: fetch arXiv source for source-assisted reading.
- `scripts/extract_figures.py`: render pages and produce figure candidates or manual-crop assets.
- `scripts/maintain_library.py`: update notes, metadata, PDFs, assets, index, and navigation idempotently.

Do not create persistent process files such as `task_plan.md`, `findings.md`, or `progress.md` unless the user explicitly asks for them.

## Verification

Match verification to the work performed:

- For local PDF/vault work: verify files exist, metadata JSON parses, PDFs are present, and index/navigation content is updated.
- For scripts: run syntax checks and focused tests.
- For index/navigation: rerun maintenance where practical and confirm no duplicate dedupe entries.
- Do not use git status as proof when the vault is not a git repository.

If network checks fail but local inputs are sufficient, continue with local evidence and report that network availability was optional.
