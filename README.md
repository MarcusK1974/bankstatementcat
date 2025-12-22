# Transformer (BASIQ Group Replication Foundation)

This repo builds deterministic ingestion, run indexing, and labeled transaction datasets for BASIQ group replication.

## Quick start

### 1) Sync data from S3 (incremental)
```bash
python3 tools/s3_sync.py \
  --profile billie \
  --bucket billie-applications-nonprod \
  --prefix demo/ \
  --dest data/raw_s3 \
  --include "*.json" \
  --include "*.html"
```

### 2) Build the run index
```bash
python3 tools/run_indexer.py --root data/raw_s3 --out data/index
```

### 3) Build the labeled dataset
```bash
python3 tools/dataset_builder.py \
  --index data/index/runs.jsonl \
  --out data/datasets \
  --groups docs/basiq_groups.yaml
```

## Outputs

- `data/raw_s3/`: S3 sync destination (gitignored)
- `data/index/`:
  - `runs.jsonl`: one run per line with grouped artifacts
  - `runs_summary.json`: aggregate counts
  - `file_inventory.csv`: file inventory by run
- `data/datasets/`:
  - `tx_labeled.csv`: labeled transaction dataset
  - `run_splits.json`: deterministic train/val/test split by run
- `data/reports/`:
  - `label_coverage.json`: label coverage and conflicts
  - `reconciliation.json`: affordability vs dataset totals

## Troubleshooting

- **Whitelist errors**: `tools/dataset_builder.py` enforces `docs/basiq_groups.yaml`. Add the full BASIQ group list (including official uncategorised EXP/INC codes) before running.
- **Missing affordability reports**: transactions without affordability signal are mapped to uncategorised codes (or `UNKNOWN` if configured).
- **Missing enrich**: enrich is optional; dataset builder handles it gracefully.
- **Determinism**: outputs are sorted and byte-stable; reruns on the same inputs should match.

## Notes

- Do not print PII to stdout; avoid logging account numbers or addresses.
- Model training is intentionally out of scope for PRP-001.
