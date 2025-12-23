from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TIMESTAMP_RE = re.compile(r"(20\d{6})(?:[_-]?(\d{6}))?")


def _parse_timestamp(text: str) -> Optional[datetime]:
    matches = list(TIMESTAMP_RE.finditer(text))
    if not matches:
        return None
    best: Optional[datetime] = None
    for match in matches:
        date = match.group(1)
        time = match.group(2) or "000000"
        try:
            dt = datetime.strptime(f"{date}{time}", "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if best is None or dt < best:
            best = dt
    return best


def _classify_path(rel_path: Path) -> str:
    parts = rel_path.parts
    if len(parts) < 3:
        return "other"
    folder = parts[2]
    name = rel_path.name
    if folder == "StatementCapture":
        if name.startswith("retrieve-transactions_"):
            return "StatementCapture/retrieve-transactions"
        if name.startswith("retrieve-accounts_"):
            return "StatementCapture/retrieve-accounts"
        if name.startswith("verify-credentials_"):
            return "StatementCapture/verify-credentials"
        return "StatementCapture/other"
    if folder == "AffordabilityReports":
        return "AffordabilityReports"
    if folder == "CreditAssessment":
        return "CreditAssessment"
    if folder == "LoanAgreement":
        return "LoanAgreement"
    return f"{folder}"


def _load_persona(path: Path) -> Optional[str]:
    try:
        with path.open() as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    profile = data.get("profile") or data.get("data", {}).get("profile") or {}
    if not isinstance(profile, dict):
        return None
    full_name = profile.get("fullName")
    if full_name:
        return str(full_name)
    first = profile.get("firstName")
    last = profile.get("lastName")
    if first or last:
        return f"{first or ''} {last or ''}".strip() or None
    return None


def _ensure_run(runs: Dict[str, dict], run_id: str) -> dict:
    if run_id not in runs:
        runs[run_id] = {
            "run_id": run_id,
            "run_prefix": f"demo/{run_id}/",
            "paths": {},
            "tx_files": [],
            "account_files": [],
            "verify_files": [],
            "affordability_files": [],
            "credit_assessment_files": [],
            "loan_agreement_files": [],
            "other_files": [],
            "persona": None,
            "run_created_at": None,
            "has_affordability_report": False,
        }
    return runs[run_id]


def _update_run_created_at(current: Optional[str], candidate: Optional[datetime]) -> Optional[str]:
    if candidate is None:
        return current
    if current:
        try:
            current_dt = datetime.fromisoformat(current)
        except ValueError:
            current_dt = None
    else:
        current_dt = None
    if current_dt is None or candidate < current_dt:
        return candidate.isoformat()
    return current


def build_index(root: Path) -> Tuple[List[dict], List[dict]]:
    runs: Dict[str, dict] = {}
    file_inventory: List[dict] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        parts = rel_path.parts
        if len(parts) < 3:
            continue
        run_id = f"{parts[0]}/{parts[1]}"
        run = _ensure_run(runs, run_id)

        category = _classify_path(rel_path)
        run["paths"].setdefault(category, []).append(rel_path.as_posix())

        if category == "StatementCapture/retrieve-transactions":
            run["tx_files"].append(rel_path.as_posix())
        elif category == "StatementCapture/retrieve-accounts":
            run["account_files"].append(rel_path.as_posix())
        elif category == "StatementCapture/verify-credentials":
            run["verify_files"].append(rel_path.as_posix())
        elif category == "AffordabilityReports":
            run["affordability_files"].append(rel_path.as_posix())
        elif category == "CreditAssessment":
            run["credit_assessment_files"].append(rel_path.as_posix())
        elif category == "LoanAgreement":
            run["loan_agreement_files"].append(rel_path.as_posix())
        else:
            run["other_files"].append(rel_path.as_posix())

        candidate = _parse_timestamp(path.name)
        if candidate is None:
            candidate = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        run["run_created_at"] = _update_run_created_at(run["run_created_at"], candidate)

        stat = path.stat()
        file_inventory.append(
            {
                "run_id": run_id,
                "artifact_type": category,
                "relative_path": rel_path.as_posix(),
                "size_bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    runs_list = []
    for run_id in sorted(runs.keys()):
        run = runs[run_id]
        for key in (
            "tx_files",
            "account_files",
            "verify_files",
            "affordability_files",
            "credit_assessment_files",
            "loan_agreement_files",
            "other_files",
        ):
            run[key] = sorted(run[key])
        run["has_affordability_report"] = len(run["affordability_files"]) > 0
        for category in sorted(run["paths"].keys()):
            run["paths"][category] = sorted(run["paths"][category])

        # Try to extract persona from verify-credentials files
        if run["verify_files"] and run["persona"] is None:
            for verify_file in run["verify_files"]:
                persona_path = root / verify_file
                persona = _load_persona(persona_path)
                if persona:
                    run["persona"] = persona
                    break
        runs_list.append(run)

    file_inventory.sort(key=lambda row: (row["run_id"], row["artifact_type"], row["relative_path"]))
    return runs_list, file_inventory


def write_outputs(out_dir: Path, runs: List[dict], file_inventory: List[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / "runs.jsonl"
    summary_path = out_dir / "runs_summary.json"
    inventory_path = out_dir / "file_inventory.csv"

    with runs_path.open("w") as f:
        for run in runs:
            f.write(json.dumps(run, sort_keys=True))
            f.write("\n")

    total_runs = len(runs)
    runs_with_affordability = sum(1 for r in runs if r.get("has_affordability_report"))
    runs_with_transactions = sum(1 for r in runs if r.get("tx_files"))
    runs_missing_transactions = total_runs - runs_with_transactions
    persona_available = sum(1 for r in runs if r.get("persona"))

    artifact_counts: Dict[str, int] = {}
    for run in runs:
        for key, items in run.get("paths", {}).items():
            artifact_counts[key] = artifact_counts.get(key, 0) + len(items)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": total_runs,
        "runs_with_affordability": runs_with_affordability,
        "runs_with_transactions": runs_with_transactions,
        "runs_missing_transactions": runs_missing_transactions,
        "persona_available": persona_available,
        "artifact_counts": dict(sorted(artifact_counts.items())),
    }
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    with inventory_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["run_id", "artifact_type", "relative_path", "size_bytes", "mtime_utc"],
        )
        writer.writeheader()
        for row in file_inventory:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a run index from downloaded S3 artifacts.")
    parser.add_argument("--root", default="data/raw_s3", help="Root folder for raw S3 artifacts")
    parser.add_argument("--out", default="data/index", help="Output directory for index files")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    runs, inventory = build_index(root)
    write_outputs(Path(args.out), runs, inventory)
    print(f"Indexed {len(runs)} runs into {args.out}")


if __name__ == "__main__":
    main()
