# Project: BASIQ Group Replication + Transaction Classification (Transformer)

## Outcome (what “done” looks like)
Build a reproducible pipeline that:
1) Ingests BASIQ-related JSON artifacts from S3 (StatementCapture, AffordabilityReports, CreditAssessment, etc.)
2) Produces a canonical, versioned dataset of transactions with features (raw + derived) and labels (BASIQ group codes)
3) Trains and evaluates a model that predicts BASIQ group codes from transaction-level inputs
4) Exposes an inference interface (CLI + Python API) that enforces the BASIQ label space strictly

## Golden Rules (non-negotiable)
1) **Never invent categories**: outputs MUST be one of the known BASIQ group codes (e.g., EXP-007). If unsure, return `UNKNOWN` (and log for review).
2) **Label space is locked**: all group codes must come from `docs/basiq_groups.yaml`. Do not add new codes unless explicitly instructed and updated in that file.
3) **Reproducibility first**:
   - Deterministic dataset build
   - Version each dataset build with a manifest (hashes + source S3 keys + timestamps)
4) **No training leakage**:
   - Split by persona/run (not random rows)
   - Keep evaluation sets isolated and immutable
5) **No silent assumptions**:
   - If a label is inferred via mapping rules (e.g., subclass->group), record the derivation method in metadata.
6) **Data safety**:
   - Do not print PII to stdout
   - Redact account numbers, card suffixes, addresses in logs
7) **Fail fast**: if required fields are missing, raise a clear error and stop; do not “make up” values.

## Repository conventions
- Raw ingested data lives in `data/raw_s3/` (gitignored).
- Derived datasets live in `data/datasets/<dataset_version>/` (gitignored, but manifests committed).
- All taxonomy files live in `docs/` and are committed.

## Current BASIQ artifact reality (important)
- S3 contains multiple JSON artifact types per run (e.g., `StatementCapture/retrieve-transactions_*.json`, `AffordabilityReports/*.json`).
- Some transaction payloads may not include `enrich`; the pipeline must handle missing enrich gracefully and rely on the best available fields.

## What to build first (priority)
1) S3 sync capability (incremental) + manifest
2) Parser that indexes runs and artifacts
3) Ground-truth label extraction strategy (transaction->group), explicitly documented
4) Baseline model (fast + interpretable), then transformer

