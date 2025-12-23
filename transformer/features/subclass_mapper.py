#!/usr/bin/env python3
"""
SubClass to BASIQ Group Mapper

NOTE: SubClass mappings are for analysis only.
DO NOT use SubClass as a training feature - it's not available in production.

This script learns mappings from BASIQ subClass codes to BASIQ group codes
based on the gold-labeled transaction dataset. The mappings help understand
BASIQ's internal categorization logic, but SubClass information is BASIQ-specific
and won't be available when processing bankstatements.com.au data in production.

For production, the model must rely on: description, amount, date, and other
universally available transaction features.

Output: data/datasets/subclass_mappings.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SubClassMapping:
    subclass_code: str
    subclass_title: str
    basiq_group_code: str
    confidence: float
    transaction_count: int
    sample_descriptions: List[str]


def learn_subclass_mappings(dataset_path: Path) -> Dict[str, SubClassMapping]:
    """
    Learn subClass → BASIQ group mappings from gold-labeled transactions.
    
    Only uses transactions with gold labels (affordability_report_id/key)
    to ensure high-quality mappings.
    """
    # Track: subclass_code → {basiq_group_code: count}
    subclass_to_groups: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Track: subclass_code → subclass_title (take most common)
    subclass_titles: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Track: (subclass_code, basiq_group_code) → sample descriptions
    sample_descs: Dict[tuple, List[str]] = defaultdict(list)
    
    print(f"Reading dataset from {dataset_path}...")
    with dataset_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            subclass_code = row.get("subclass_code", "").strip()
            subclass_title = row.get("subclass_title", "").strip()
            label_code = row.get("label_group_code", "").strip()
            label_source = row.get("label_source", "").strip()
            description = row.get("description", "").strip()
            
            # Only learn from gold labels (not rules or fallbacks)
            if label_source not in {"affordability_report_id", "affordability_report_key"}:
                continue
            
            # Skip if no subclass
            if not subclass_code or not label_code:
                continue
            
            # Count mapping
            subclass_to_groups[subclass_code][label_code] += 1
            
            # Track title
            if subclass_title:
                subclass_titles[subclass_code][subclass_title] += 1
            
            # Collect sample descriptions (max 5)
            key = (subclass_code, label_code)
            if len(sample_descs[key]) < 5:
                sample_descs[key].append(description)
    
    # Build final mappings with confidence scores
    mappings: Dict[str, SubClassMapping] = {}
    
    for subclass_code, group_counts in sorted(subclass_to_groups.items()):
        # Determine the most common BASIQ group for this subclass
        total_count = sum(group_counts.values())
        most_common_group = max(group_counts.items(), key=lambda x: x[1])
        basiq_group_code = most_common_group[0]
        group_count = most_common_group[1]
        confidence = group_count / total_count
        
        # Get most common title
        if subclass_code in subclass_titles:
            most_common_title = max(
                subclass_titles[subclass_code].items(),
                key=lambda x: x[1]
            )[0]
        else:
            most_common_title = ""
        
        # Get sample descriptions
        samples = sample_descs.get((subclass_code, basiq_group_code), [])
        
        mapping = SubClassMapping(
            subclass_code=subclass_code,
            subclass_title=most_common_title,
            basiq_group_code=basiq_group_code,
            confidence=confidence,
            transaction_count=total_count,
            sample_descriptions=samples,
        )
        mappings[subclass_code] = mapping
    
    return mappings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Learn subClass → BASIQ group mappings from gold-labeled data."
    )
    parser.add_argument(
        "--dataset",
        default="data/datasets/tx_labeled.csv",
        help="Path to labeled transaction dataset CSV",
    )
    parser.add_argument(
        "--out",
        default="data/datasets/subclass_mappings.json",
        help="Output path for mappings JSON",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Minimum confidence threshold to include mapping (0-1)",
    )
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    out_path = Path(args.out)
    
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")
    
    mappings = learn_subclass_mappings(dataset_path)
    
    # Filter by confidence threshold
    high_confidence = {
        code: mapping
        for code, mapping in mappings.items()
        if mapping.confidence >= args.min_confidence
    }
    
    low_confidence = {
        code: mapping
        for code, mapping in mappings.items()
        if mapping.confidence < args.min_confidence
    }
    
    # Serialize to JSON
    output = {
        "high_confidence_mappings": {
            code: {
                "subclass_code": m.subclass_code,
                "subclass_title": m.subclass_title,
                "basiq_group_code": m.basiq_group_code,
                "confidence": round(m.confidence, 4),
                "transaction_count": m.transaction_count,
                "sample_descriptions": m.sample_descriptions,
            }
            for code, m in sorted(high_confidence.items())
        },
        "low_confidence_mappings": {
            code: {
                "subclass_code": m.subclass_code,
                "subclass_title": m.subclass_title,
                "basiq_group_code": m.basiq_group_code,
                "confidence": round(m.confidence, 4),
                "transaction_count": m.transaction_count,
                "note": "Multiple BASIQ groups observed - review manually",
            }
            for code, m in sorted(low_confidence.items())
        },
        "summary": {
            "total_subclasses_found": len(mappings),
            "high_confidence_count": len(high_confidence),
            "low_confidence_count": len(low_confidence),
            "min_confidence_threshold": args.min_confidence,
        },
    }
    
    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2, sort_keys=True)
    
    print(f"\nWrote mappings to {out_path}")
    print(f"\nSummary:")
    print(f"  Total subClasses found: {len(mappings)}")
    print(f"  High confidence (≥{args.min_confidence}): {len(high_confidence)}")
    print(f"  Low confidence (<{args.min_confidence}): {len(low_confidence)}")
    print(f"\nExample high-confidence mappings:")
    for code, m in list(high_confidence.items())[:5]:
        print(f"  {code} ({m.subclass_title}) → {m.basiq_group_code} "
              f"({m.confidence:.1%} confidence, {m.transaction_count} txs)")


if __name__ == "__main__":
    main()

