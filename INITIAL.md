## FEATURE:
Build an ingestion + dataset foundation for BASIQ group replication.

Must include:
1) Config-driven S3 sync that downloads all current artifacts and can be re-run to fetch new files incrementally.
2) A run indexer that groups artifacts by run folder prefix (e.g., demo/<A>/<B>/...) and exposes a machine-readable index.
3) A dataset builder that extracts transaction rows and attaches the best-available label signals, without inventing labels.

## EXAMPLES:
- examples/ should include at least:
  - a minimal “parse a BASIQ transaction JSON into canonical fields” example
  - a minimal “build a manifest and write it deterministically” example

## DOCUMENTATION:
- BASIQ group codes are locked to docs/basiq_groups.yaml.
- AWS S3 sync uses AWS CLI profile (SSO) and must not require static keys.

## OTHER CONSIDERATIONS:
- Some transaction artifacts may lack `enrich`. Code must handle missing keys.
- Avoid data leakage: implement split-by-run scaffolding early.
- Do not add new BASIQ group codes without explicit instruction.

