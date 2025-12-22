# Labeling Strategy (Draft)

Goal: produce transaction-level labels in the locked BASIQ group code space.

Important reality:
- Some stored transaction payloads may not contain enrich fields.
- Affordability report artifacts contain group-level totals and UI breakdowns, but may not always include transaction-level group annotations directly.

Strategy options (in order of preference):
1) If any artifact includes transaction->group attribution, treat that as gold labels.
2) Otherwise, derive group labels via a deterministic mapping table from stable transaction attributes
   (e.g., subClass.code/title, ANZSIC group code/title, merchant id/name) to BASIQ group codes,
   learned from observed examples and then locked/versioned as a ruleset.

All derived labels must record:
- derivation_method: GOLD | RULE_SUBCLASS | RULE_ANZSIC | RULE_MERCHANT | UNKNOWN
- derivation_version: e.g., rules_v1
