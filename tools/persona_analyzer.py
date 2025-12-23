from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RunQuality:
    run_id: str
    persona: Optional[str]
    transaction_count: int
    has_affordability: bool
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    date_range_days: int
    completeness_score: float  # 0-1, based on having all artifact types


def _load_runs(index_path: Path) -> List[dict]:
    """Load runs from JSONL index file."""
    runs = []
    with index_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


def _calculate_completeness(run: dict) -> float:
    """Calculate completeness score based on available artifacts."""
    score = 0.0
    # Has transactions (most important)
    if run.get("tx_files"):
        score += 0.4
    # Has affordability report (critical for labels)
    if run.get("has_affordability_report"):
        score += 0.4
    # Has verify credentials (for persona)
    if run.get("verify_files"):
        score += 0.1
    # Has account files
    if run.get("account_files"):
        score += 0.05
    # Has credit assessment
    if run.get("credit_assessment_files"):
        score += 0.05
    return score


def _estimate_transaction_count(run: dict) -> int:
    """Estimate transaction count based on number of transaction files."""
    # Rough estimate: each transaction file has ~400-600 transactions
    # But we'd need to actually parse them to know for sure
    return len(run.get("tx_files", [])) * 500


def _parse_date_range(run: dict) -> tuple[Optional[str], Optional[str], int]:
    """Parse date range from run_created_at."""
    created_at = run.get("run_created_at")
    if not created_at:
        return None, None, 0
    
    # For now, we just use the run creation date as a proxy
    # In reality, we'd need to parse transactions to get actual range
    return created_at, created_at, 0


def analyze_personas(index_path: Path) -> Dict[str, any]:
    """Analyze persona distribution and run quality across all runs."""
    runs = _load_runs(index_path)
    
    # Group runs by persona
    persona_runs: Dict[Optional[str], List[RunQuality]] = defaultdict(list)
    
    for run in runs:
        persona = run.get("persona")
        run_id = run.get("run_id", "")
        tx_count = _estimate_transaction_count(run)
        has_affordability = run.get("has_affordability_report", False)
        completeness = _calculate_completeness(run)
        date_start, date_end, days = _parse_date_range(run)
        
        quality = RunQuality(
            run_id=run_id,
            persona=persona,
            transaction_count=tx_count,
            has_affordability=has_affordability,
            date_range_start=date_start,
            date_range_end=date_end,
            date_range_days=days,
            completeness_score=completeness,
        )
        persona_runs[persona].append(quality)
    
    # Analyze each persona
    persona_analysis = {}
    for persona, runs_list in sorted(persona_runs.items(), key=lambda x: (x[0] is None, x[0])):
        # Sort runs by quality (completeness, then transaction count)
        runs_list.sort(key=lambda r: (r.completeness_score, r.transaction_count), reverse=True)
        
        total_tx = sum(r.transaction_count for r in runs_list)
        avg_completeness = sum(r.completeness_score for r in runs_list) / len(runs_list)
        with_affordability = sum(1 for r in runs_list if r.has_affordability)
        
        persona_analysis[persona or "unknown"] = {
            "persona": persona,
            "run_count": len(runs_list),
            "estimated_total_transactions": total_tx,
            "avg_completeness_score": round(avg_completeness, 3),
            "runs_with_affordability": with_affordability,
            "best_runs": [
                {
                    "run_id": r.run_id,
                    "estimated_tx_count": r.transaction_count,
                    "completeness_score": round(r.completeness_score, 3),
                    "has_affordability": r.has_affordability,
                    "date_range_start": r.date_range_start,
                }
                for r in runs_list[:5]  # Top 5 runs
            ],
        }
    
    # Generate train/test split recommendation
    personas = [p for p in persona_runs.keys() if p is not None]
    
    # Recommend using personas with fewer runs for test (less data to waste)
    # and persona with most runs for training
    persona_by_count = sorted(
        [(p, len(persona_runs[p])) for p in personas],
        key=lambda x: x[1]
    )
    
    if len(persona_by_count) >= 2:
        test_personas = [p[0] for p in persona_by_count[:2]]  # 2 smallest
        train_personas = [p[0] for p in persona_by_count[2:]]  # Rest for training
    else:
        test_personas = []
        train_personas = [p[0] for p in persona_by_count]
    
    recommendation = {
        "strategy": "persona-based split (zero leakage)",
        "test_personas": test_personas,
        "train_personas": train_personas,
        "rationale": {
            "test": "Use personas with fewest runs to minimize wasted data",
            "train": "Use persona with most runs for maximum training data",
            "note": "Max Wentworth-Smith has 33 runs - select best 1-3 for training to avoid overfitting",
        },
    }
    
    # Summary statistics
    total_runs = len(runs)
    total_personas = len([p for p in personas if p is not None])
    runs_with_affordability = sum(1 for run in runs if run.get("has_affordability_report"))
    runs_with_tx = sum(1 for run in runs if run.get("tx_files"))
    
    summary = {
        "total_runs": total_runs,
        "total_personas": total_personas,
        "runs_with_affordability": runs_with_affordability,
        "runs_with_transactions": runs_with_tx,
        "runs_missing_persona": len(persona_runs.get(None, [])),
    }
    
    return {
        "summary": summary,
        "personas": persona_analysis,
        "recommended_split": recommendation,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze persona distribution and run quality for BASIQ dataset."
    )
    parser.add_argument(
        "--index",
        default="data/index/runs.jsonl",
        help="Path to runs index JSONL file",
    )
    parser.add_argument(
        "--out",
        default="data/reports/persona_analysis.json",
        help="Output path for analysis JSON",
    )
    args = parser.parse_args()
    
    index_path = Path(args.index)
    out_path = Path(args.out)
    
    if not index_path.exists():
        raise SystemExit(f"Index file not found: {index_path}")
    
    print(f"Analyzing personas from {index_path}...")
    analysis = analyze_personas(index_path)
    
    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(analysis, f, indent=2, sort_keys=True)
    
    print(f"\nWrote analysis to {out_path}")
    print(f"\nSummary:")
    print(f"  Total runs: {analysis['summary']['total_runs']}")
    print(f"  Unique personas: {analysis['summary']['total_personas']}")
    print(f"  Runs with affordability: {analysis['summary']['runs_with_affordability']}")
    print(f"\nPersonas found:")
    for persona_name, data in analysis['personas'].items():
        if persona_name != "unknown":
            print(f"  - {persona_name}: {data['run_count']} runs, "
                  f"~{data['estimated_total_transactions']} transactions")
    
    print(f"\nRecommended split:")
    rec = analysis['recommended_split']
    print(f"  Test: {', '.join(rec['test_personas'])}")
    print(f"  Train: {', '.join(rec['train_personas'])}")


if __name__ == "__main__":
    main()

