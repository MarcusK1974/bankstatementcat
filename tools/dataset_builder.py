from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class GroupInfo:
    code: str
    name: str = ""


def _safe_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _normalize_desc(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(str(text).strip().lower().split())


def _normalize_date(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text)
    if len(text) >= 10:
        return text[:10]
    return text


def _build_key(description: Optional[str], amount: Optional[Decimal], date: Optional[str]) -> Optional[Tuple[str, str, str]]:
    if amount is None:
        return None
    desc = _normalize_desc(description)
    date_key = _normalize_date(date)
    if not desc or not date_key:
        return None
    return (desc, _format_amount(amount), date_key)


def _load_groups(path: Path) -> Tuple[List[GroupInfo], List[str], Dict[str, str]]:
    try:
        import yaml  # type: ignore

        with path.open() as f:
            data = yaml.safe_load(f)
        groups_raw = data.get("groups", []) if isinstance(data, dict) else []
        uncategorised: Dict[str, str] = {}
        if isinstance(data, dict):
            uncategorised_raw = data.get("uncategorised") or data.get("uncategorized") or {}
            if isinstance(uncategorised_raw, dict):
                expense = uncategorised_raw.get("expense")
                income = uncategorised_raw.get("income")
                if expense:
                    uncategorised["expense"] = str(expense)
                if income:
                    uncategorised["income"] = str(income)
        groups: List[GroupInfo] = []
        codes: List[str] = []
        for item in groups_raw:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            if not code:
                continue
            name = item.get("name", "")
            groups.append(GroupInfo(code=str(code), name=str(name)))
            codes.append(str(code))
        return groups, codes, uncategorised
    except ImportError:
        groups = []
        codes = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line.startswith("- code:"):
                code = line.split(":", 1)[1].strip().strip("\"").strip("'")
                if code:
                    groups.append(GroupInfo(code=code))
                    codes.append(code)
        return groups, codes, {}


def _resolve_uncategorised(
    groups: List[GroupInfo],
    codes: List[str],
    overrides: Optional[Dict[str, str]] = None,
) -> Tuple[str, str, bool]:
    expense_candidates: List[str] = []
    income_candidates: List[str] = []

    for group in groups:
        name = group.name.lower()
        code = group.code
        if "uncategor" not in name:
            continue
        if "income" in name or code.startswith("INC"):
            income_candidates.append(code)
        if "expense" in name or code.startswith("EXP"):
            expense_candidates.append(code)

    expense = sorted(set(expense_candidates))[0] if expense_candidates else None
    income = sorted(set(income_candidates))[0] if income_candidates else None

    overrides = overrides or {}
    expense_override = overrides.get("expense")
    income_override = overrides.get("income")
    if expense_override:
        expense = expense_override
    if income_override:
        income = income_override

    fallback_used = False
    if (not expense or not income) and "UNKNOWN" in codes:
        fallback_used = True
        if not expense:
            expense = "UNKNOWN"
        if not income:
            income = "UNKNOWN"

    if not expense or not income:
        raise ValueError(
            "Uncategorised group codes not found in docs/basiq_groups.yaml. "
            "Add official uncategorised EXP/INC codes or an UNKNOWN fallback."
        )

    if expense not in codes or income not in codes:
        raise ValueError("Resolved uncategorised codes are not in the whitelist.")

    return expense, income, fallback_used


def _load_runs(index_path: Path) -> List[dict]:
    runs = []
    with index_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


def _assign_split(run_id: str) -> str:
    """Legacy run-based split (for backwards compatibility)."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    if value < 0.7:
        return "train"
    if value < 0.85:
        return "val"
    return "test"


def _assign_persona_split(persona: Optional[str], persona_analysis: dict) -> str:
    """Persona-based split strategy to prevent data leakage."""
    # Use recommendations from persona analysis
    recommended = persona_analysis.get("recommended_split", {})
    
    if persona in recommended.get("test_personas", []):
        return "test"
    elif persona in recommended.get("train_personas", []):
        return "train"
    else:
        # Unknown personas go to val for review
        return "val"


def _extract_transactions(path: Path) -> List[dict]:
    with path.open() as f:
        data = json.load(f)
    if isinstance(data, dict):
        items = data.get("data") or data.get("transactions") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    if not isinstance(items, list):
        return []
    return items


def _extract_affordability_groups(path: Path) -> List[dict]:
    with path.open() as f:
        data = json.load(f)
    groups = data.get("data", {}).get("groups", []) if isinstance(data, dict) else []
    return groups if isinstance(groups, list) else []


def _extract_group_totals(groups: List[dict]) -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    for group in groups:
        code = group.get("id")
        if not code:
            continue
        code = str(code)
        amount = group.get("analysis", {}).get("amount", {}).get("total")
        dec = _safe_decimal(amount)
        if dec is None:
            continue
        totals[code] = totals.get(code, Decimal("0.00")) + dec
    return totals


def _extract_affordability_mappings(
    groups: List[dict],
    whitelist: set,
    report_path: str,
    id_map: Dict[str, dict],
    key_map: Dict[Tuple[str, str, str], dict],
    conflicts: Dict[str, set],
) -> None:
    def record_by_id(tx_id: str, code: str) -> None:
        if tx_id in id_map and id_map[tx_id]["code"] != code:
            conflicts.setdefault("id", set()).add(tx_id)
            id_map.pop(tx_id, None)
            return
        id_map[tx_id] = {"code": code, "path": report_path}

    def record_by_key(key: Tuple[str, str, str], code: str) -> None:
        if key in key_map and key_map[key]["code"] != code:
            conflicts.setdefault("key", set()).add("|".join(key))
            key_map.pop(key, None)
            return
        key_map[key] = {"code": code, "path": report_path}

    for group in groups:
        code = group.get("id")
        if not code:
            continue
        code = str(code)
        if code not in whitelist:
            raise ValueError(f"Affordability group code not in whitelist: {code}")

        for tx in group.get("transactions", []) or []:
            tx_id = tx.get("id")
            if tx_id:
                record_by_id(str(tx_id), code)
                continue
            amount = _safe_decimal(tx.get("amount"))
            key = _build_key(tx.get("description"), amount, tx.get("date"))
            if key:
                record_by_key(key, code)

        for subgroup in group.get("subgroup", []) or []:
            for tx in subgroup.get("transactions", []) or []:
                tx_id = tx.get("id")
                if tx_id:
                    record_by_id(str(tx_id), code)
                    continue
                amount = _safe_decimal(tx.get("amount"))
                key = _build_key(tx.get("description"), amount, tx.get("date"))
                if key:
                    record_by_key(key, code)


def _extract_enrich_fields(enrich: object) -> Tuple[str, str, str, str]:
    merchant_name = ""
    clean_description = ""
    anzsic_group_code = ""
    anzsic_group_title = ""

    if isinstance(enrich, dict):
        clean_description = (
            enrich.get("cleanDescription")
            or enrich.get("clean_description")
            or enrich.get("clean")
            or ""
        )
        merchant = enrich.get("merchant") or {}
        if isinstance(merchant, dict):
            merchant_name = merchant.get("name") or ""
        anzsic = enrich.get("anzsic") or {}
        if isinstance(anzsic, dict):
            group = anzsic.get("group") or {}
            if isinstance(group, dict):
                anzsic_group_code = group.get("code") or ""
                anzsic_group_title = group.get("title") or ""
            else:
                anzsic_group_code = anzsic.get("groupCode") or ""
                anzsic_group_title = anzsic.get("groupTitle") or ""

    return (
        str(merchant_name) if merchant_name else "",
        str(clean_description) if clean_description else "",
        str(anzsic_group_code) if anzsic_group_code else "",
        str(anzsic_group_title) if anzsic_group_title else "",
    )


def build_dataset(
    index_path: Path,
    groups_path: Path,
    out_dir: Path,
    reports_dir: Path,
    raw_root: Path,
) -> None:
    groups, codes, uncategorised = _load_groups(groups_path)
    whitelist = set(codes)
    if not whitelist:
        raise ValueError("No group codes found in docs/basiq_groups.yaml")

    expense_uncat, income_uncat, fallback_used = _resolve_uncategorised(
        groups, codes, uncategorised
    )

    runs = _load_runs(index_path)
    runs_sorted = sorted(runs, key=lambda r: r.get("run_id", ""))
    
    # Load persona analysis for split recommendations
    persona_analysis_path = reports_dir / "persona_analysis.json"
    persona_analysis = {}
    if persona_analysis_path.exists():
        with persona_analysis_path.open() as f:
            persona_analysis = json.load(f)
    else:
        print(f"Warning: No persona analysis found at {persona_analysis_path}")
        print("Using default split strategy")

    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    tx_rows: List[dict] = []
    coverage = {
        "total_transactions": 0,
        "labeled_by_id": 0,
        "labeled_by_key": 0,
        "uncategorised": 0,
        "missing_affordability": 0,
        "rule_transfer": 0,
        "rule_interest": 0,
        "rule_online_retail": 0,
        "conflicts": {"id": 0, "key": 0},
        "fallback_unknown_used": fallback_used,
        "per_run": [],
    }

    reconciliation = {"runs": []}

    dataset_totals_by_run: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    for run in runs_sorted:
        run_id = run.get("run_id")
        if not run_id:
            continue
        tx_files = [str(path) for path in run.get("tx_files", [])]
        affordability_files = [
            str(path) for path in run.get("affordability_files", [])
        ]

        run_counts = {
            "run_id": run_id,
            "total_transactions": 0,
            "labeled_by_id": 0,
            "labeled_by_key": 0,
            "uncategorised": 0,
            "missing_affordability": 0,
            "rule_transfer": 0,
            "rule_interest": 0,
            "rule_online_retail": 0,
            "conflicts": {"id": 0, "key": 0},
        }

        transactions_by_id: Dict[str, dict] = {}
        transactions_by_key: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
        duplicates: set = set()

        for path_str in sorted(tx_files):
            path = raw_root / path_str
            items = _extract_transactions(path)
            for tx in items:
                tx_id = str(tx.get("id") or "").strip()
                if not tx_id:
                    raise ValueError(f"Missing transaction id in {path}")
                if tx_id in transactions_by_id:
                    duplicates.add(tx_id)
                    continue

                amount = _safe_decimal(tx.get("amount"))
                if amount is None:
                    raise ValueError(f"Missing/invalid amount for transaction {tx_id}")
                direction = str(tx.get("direction") or "").lower()
                if direction not in {"debit", "credit"}:
                    raise ValueError(f"Missing/invalid direction for transaction {tx_id}")

                description = str(tx.get("description") or "")
                transaction_date = tx.get("transactionDate") or ""
                post_date = tx.get("postDate") or ""

                merchant_name, clean_description, anzsic_code, anzsic_title = _extract_enrich_fields(
                    tx.get("enrich")
                )
                
                # Extract subClass fields (available even when enrich is null)
                subclass = tx.get("subClass") or {}
                subclass_code = ""
                subclass_title = ""
                if isinstance(subclass, dict):
                    subclass_code = str(subclass.get("code") or "")
                    subclass_title = str(subclass.get("title") or "")

                record = {
                    "run_id": run_id,
                    "transaction_id": tx_id,
                    "direction": direction,
                    "amount": _format_amount(amount),
                    "description": description,
                    "clean_description": clean_description,
                    "merchant_name": merchant_name,
                    "subclass_code": subclass_code,
                    "subclass_title": subclass_title,
                    "anzsic_group_code": anzsic_code,
                    "anzsic_group_title": anzsic_title,
                    "post_date": post_date,
                    "transaction_date": transaction_date,
                    "raw_path": path_str,
                }
                transactions_by_id[tx_id] = record

                key = _build_key(description, amount, transaction_date or post_date)
                if key:
                    transactions_by_key[key].append(tx_id)

        id_map: Dict[str, dict] = {}
        key_map: Dict[Tuple[str, str, str], dict] = {}
        conflicts: Dict[str, set] = {}
        group_totals_affordability: List[dict] = []

        for report_str in sorted(affordability_files):
            report_path = raw_root / report_str
            groups_list = _extract_affordability_groups(report_path)
            _extract_affordability_mappings(
                groups_list,
                whitelist,
                report_str,
                id_map,
                key_map,
                conflicts,
            )
            totals = _extract_group_totals(groups_list)
            if totals:
                group_totals_affordability.append(
                    {
                        "report_path": report_str,
                        "group_totals": {k: _format_amount(v) for k, v in sorted(totals.items())},
                    }
                )

        run_counts["conflicts"]["id"] = len(conflicts.get("id", set()))
        run_counts["conflicts"]["key"] = len(conflicts.get("key", set()))

        for tx_id in sorted(transactions_by_id.keys()):
            record = transactions_by_id[tx_id]
            label_code = ""
            label_source = ""
            affordability_path = ""
            desc_lower = _normalize_desc(record["description"])
            amount_dec = _safe_decimal(record["amount"])

            if tx_id in id_map:
                label_code = id_map[tx_id]["code"]
                affordability_path = id_map[tx_id]["path"]
                label_source = "affordability_report_id"
                run_counts["labeled_by_id"] += 1
            else:
                key = _build_key(
                    record["description"],
                    amount_dec,
                    record["transaction_date"] or record["post_date"],
                )
                if key and key in key_map and len(transactions_by_key.get(key, [])) == 1:
                    label_code = key_map[key]["code"]
                    affordability_path = key_map[key]["path"]
                    label_source = "affordability_report_key"
                    run_counts["labeled_by_key"] += 1
                else:
                    conflict_id = tx_id in conflicts.get("id", set())
                    conflict_key = False
                    if key:
                        conflict_key = "|".join(key) in conflicts.get("key", set())
                    if (conflict_id or conflict_key) and ".com" in desc_lower:
                        label_code = "EXP-024"
                        label_source = "rule_online_retail"
                        run_counts.setdefault("rule_online_retail", 0)
                        run_counts["rule_online_retail"] += 1
                    elif "transfer" in desc_lower:
                        label_code = "EXP-013"
                        label_source = "rule_transfer"
                        run_counts.setdefault("rule_transfer", 0)
                        run_counts["rule_transfer"] += 1
                    elif "interest" in desc_lower and amount_dec is not None:
                        if amount_dec < 0:
                            label_code = "EXP-006"
                            label_source = "rule_interest_debit"
                        else:
                            label_code = "INC-004"
                            label_source = "rule_interest_credit"
                        run_counts.setdefault("rule_interest", 0)
                        run_counts["rule_interest"] += 1
                    else:
                        if not affordability_files:
                            run_counts["missing_affordability"] += 1
                        if record["direction"] == "credit":
                            label_code = income_uncat
                        else:
                            label_code = expense_uncat
                        label_source = "fallback_uncategorised"
                        run_counts["uncategorised"] += 1

            if label_code not in whitelist:
                raise ValueError(f"Label code not in whitelist: {label_code}")

            record["label_group_code"] = label_code
            record["label_source"] = label_source
            record["affordability_path"] = affordability_path
            tx_rows.append(record)

            amount = _safe_decimal(record["amount"])
            if amount is not None:
                dataset_totals_by_run[run_id][label_code] += amount

        run_counts["total_transactions"] = len(transactions_by_id)
        coverage["total_transactions"] += run_counts["total_transactions"]
        coverage["labeled_by_id"] += run_counts["labeled_by_id"]
        coverage["labeled_by_key"] += run_counts["labeled_by_key"]
        coverage["uncategorised"] += run_counts["uncategorised"]
        coverage["missing_affordability"] += run_counts["missing_affordability"]
        coverage["rule_transfer"] += run_counts["rule_transfer"]
        coverage["rule_interest"] += run_counts["rule_interest"]
        coverage["rule_online_retail"] += run_counts["rule_online_retail"]
        coverage["conflicts"]["id"] += run_counts["conflicts"]["id"]
        coverage["conflicts"]["key"] += run_counts["conflicts"]["key"]
        coverage["per_run"].append(run_counts)

        if group_totals_affordability:
            dataset_totals = dataset_totals_by_run.get(run_id, {})
            dataset_totals_str = {k: _format_amount(v) for k, v in sorted(dataset_totals.items())}
            rec_reports = []
            for report in group_totals_affordability:
                report_totals = report["group_totals"]
                delta = {}
                for code, total in report_totals.items():
                    dataset_total = dataset_totals.get(code, Decimal("0.00"))
                    delta[code] = _format_amount(dataset_total - Decimal(total))
                rec_reports.append(
                    {
                        "report_path": report["report_path"],
                        "group_totals_affordability": report_totals,
                        "group_totals_dataset": dataset_totals_str,
                        "delta": delta,
                    }
                )
            reconciliation["runs"].append({"run_id": run_id, "reports": rec_reports})

    tx_rows.sort(key=lambda r: (r["run_id"], r["transaction_id"]))

    output_path = out_dir / "tx_labeled.csv"
    fieldnames = [
        "run_id",
        "transaction_id",
        "direction",
        "amount",
        "description",
        "clean_description",
        "merchant_name",
        "subclass_code",
        "subclass_title",
        "anzsic_group_code",
        "anzsic_group_title",
        "post_date",
        "transaction_date",
        "label_group_code",
        "label_source",
        "raw_path",
        "affordability_path",
    ]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in tx_rows:
            writer.writerow(row)

    # Build persona-aware splits
    splits = {"train": [], "val": [], "test": []}
    persona_to_runs: Dict[Optional[str], List[str]] = defaultdict(list)
    
    for run in runs_sorted:
        run_id = run.get("run_id")
        persona = run.get("persona")
        if not run_id:
            continue
        persona_to_runs[persona].append(run_id)
    
    # Assign splits by persona (prevent leakage)
    for persona, run_ids in persona_to_runs.items():
        split = _assign_persona_split(persona, persona_analysis)
        splits[split].extend(run_ids)
    
    for key in splits:
        splits[key] = sorted(splits[key])
    
    # Get actual split strategy description
    split_strategy = "persona-based"
    if persona_analysis:
        test_personas = persona_analysis.get("recommended_split", {}).get("test_personas", [])
        train_personas = persona_analysis.get("recommended_split", {}).get("train_personas", [])
        split_strategy = f"persona-based (test: {', '.join(test_personas)}, train: {', '.join(train_personas)})"

    splits_path = out_dir / "run_splits.json"
    with splits_path.open("w") as f:
        json.dump(
            {
                "splits": splits,
                "counts": {k: len(v) for k, v in splits.items()},
                "strategy": split_strategy,
                "personas": {
                    "train": sorted(set(
                        run.get("persona")
                        for run in runs_sorted
                        if run.get("run_id") in splits["train"] and run.get("persona")
                    )),
                    "val": sorted(set(
                        run.get("persona")
                        for run in runs_sorted
                        if run.get("run_id") in splits["val"] and run.get("persona")
                    )),
                    "test": sorted(set(
                        run.get("persona")
                        for run in runs_sorted
                        if run.get("run_id") in splits["test"] and run.get("persona")
                    )),
                },
            },
            f,
            indent=2,
            sort_keys=True,
        )

    coverage_path = reports_dir / "label_coverage.json"
    with coverage_path.open("w") as f:
        json.dump(coverage, f, indent=2, sort_keys=True)

    reconciliation_path = reports_dir / "reconciliation.json"
    with reconciliation_path.open("w") as f:
        json.dump(reconciliation, f, indent=2, sort_keys=True)

    print(f"Wrote {output_path}")
    print(f"Wrote {splits_path}")
    print(f"Wrote {coverage_path}")
    print(f"Wrote {reconciliation_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a labeled transaction dataset.")
    parser.add_argument("--index", default="data/index/runs.jsonl", help="Run index JSONL")
    parser.add_argument("--out", default="data/datasets", help="Dataset output directory")
    parser.add_argument("--groups", default="docs/basiq_groups.yaml", help="BASIQ group whitelist YAML")
    parser.add_argument("--reports", default="data/reports", help="Reports output directory")
    parser.add_argument("--raw-root", default="data/raw_s3", help="Root folder for raw artifacts")
    args = parser.parse_args()

    build_dataset(
        Path(args.index),
        Path(args.groups),
        Path(args.out),
        Path(args.reports),
        Path(args.raw_root),
    )


if __name__ == "__main__":
    main()
