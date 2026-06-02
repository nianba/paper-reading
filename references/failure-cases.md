# Failure Cases

Use this reference when paper extraction, figures, source files, or vault maintenance behave unexpectedly.

## Noisy PDF Text

Symptom: explanations feel out of order or sections are mixed.

Cause: two-column or complex PDFs can produce layout-extracted text in the wrong order.

Do differently:

- Compare raw text, rendered pages, and arXiv source when available.
- Use the PDF as canonical evidence.
- Do not summarize from noisy extracted text alone.

## Overconfident Figure Extraction

Symptom: extracted images are weak, cropped incorrectly, or unrelated to the intended figure.

Cause: caption detection and automatic cropping are only heuristics.

Do differently:

- Treat `extract_figures.py` output as candidates.
- Inspect diagnostics and rendered pages.
- Use manual crop coordinates for important framework or result figures.
- Do not block note generation because figure extraction failed.

## Local Workflow Blocked By Network

Symptom: a local PDF task is reported as broken because arXiv or another network source timed out.

Cause: local readiness and network availability were conflated.

Do differently:

- Use `doctor.py` and distinguish `local_ok` from `network_ok`.
- Continue when `local_ok` is true and the local PDF is sufficient.
- Report network failure as optional unless the requested source requires downloading.

## Duplicate Figure Blocks

Symptom: a note contains repeated figure sections after maintenance reruns.

Cause: figure insertion used both hand-written blocks and manifest-driven insertion.

Do differently:

- Choose exactly one insertion path.
- If using manifest-driven insertion, replace the managed figure block idempotently.
- Verify the final note once after rerun.

## Duplicate Index Entries

Symptom: `Papers Index.md` or navigation pages gain duplicate entries.

Cause: display cleanup changed the visible entry but ignored the stable dedupe key.

Do differently:

- Keep dedupe markers or another stable dedupe mechanism.
- Use `arxiv:<id-without-version>` when arXiv ID exists.
- Rerun maintenance and confirm one entry per dedupe key.

## Wrong Verification Surface

Symptom: a vault task is considered unverified because `git status` fails.

Cause: the paper vault may not be a git repository.

Do differently:

- Verify file existence, JSON validity, PDF presence, and index/navigation content.
- Use git only when the target directory is actually a git repository.
