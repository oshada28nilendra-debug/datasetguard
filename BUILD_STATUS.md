# DatasetGuard build record — 2026-10-13

Implemented the approved computer-vision dataset QA MVP in the authorized `oshada28nilendra-debug/datasetguard` repository. Initial inspection found only a README on main and no existing branches, PRs or repository instructions. Work is submitted on `feat/datasetguard-mvp`; no merge, deployment, or source-image modification was performed.

## Verified locally

- Python 3.12: `python -m pytest -q` — **13 passed**.
- Synthetic evaluation: 16 images across train/validation/test; three known cross-split transformed duplicates, five held-out unrelated images. At dHash-256 threshold 12: **3 true positives, 0 false positives, 0 false negatives, precision 1.0, recall 1.0**. Scan time: see the machine-specific committed report.
- Chromium browser: ZIP upload, three rendered candidates, human review selection, reviewed JSON download, zero destructive actions, responsive 390px layout and zero page errors passed.
- Failure/security coverage includes invalid thresholds/splits, corrupt images, byte-vs-pixel identity, unknown review candidates, invalid decisions, ZIP path traversal and invalid ZIP layouts.

The fixture is original, deterministic and synthetic. It is intentionally small; results do not estimate performance on a real dataset. dHash can miss rotations/crops and can create false positives on visually simple images. There is no production deployment or user-adoption claim.

CI repeats the tests, evaluation and browser workflow, then retains report/screenshot artifacts. Remote status must be read from the PR checks rather than inferred from this local record.
