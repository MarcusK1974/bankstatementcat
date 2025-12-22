# Project Status

## Summary
- S3 sync tool updated to write a deterministic manifest with file inventory.
- Run indexer implemented and successfully generated `data/index/runs.jsonl` and `data/index/runs_summary.json`.
- Dataset builder implemented with whitelist enforcement, affordability label joins, uncategorised fallback, and deterministic run splits.
- Examples added for transaction parsing and manifest generation; README updated with the PRP-001 workflow.

## Current Outputs
- Run indexer was executed: `python3 tools/run_indexer.py --root data/raw_s3 --out data/index` (indexed 36 runs).
- Dataset builder has not been executed yet because `docs/basiq_groups.yaml` is still a starter subset.

## Recommended Next Steps
1) Populate `docs/basiq_groups.yaml` with the full BASIQ group whitelist, including the official uncategorised EXP/INC codes (or keep `UNKNOWN` as a fallback).
2) Re-run S3 sync to generate the new manifest format:
   `python3 tools/s3_sync.py --profile billie --bucket billie-applications-nonprod --prefix demo/ --dest data/raw_s3 --include "*.json" --include "*.html"`
3) Build the labeled dataset:
   `python3 tools/dataset_builder.py --index data/index/runs.jsonl --out data/datasets --groups docs/basiq_groups.yaml`
4) Review reports:
   - `data/reports/label_coverage.json`
   - `data/reports/reconciliation.json`
