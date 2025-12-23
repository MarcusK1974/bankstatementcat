#!/usr/bin/env python3
"""
Feature Extractor for Production ML Training

Extracts ONLY production-ready features from transactions.
SubClass and ANZSIC features are excluded because they are BASIQ-specific
and won't be available when processing bankstatements.com.au data.

Production-available features:
- description (text)
- amount (numeric)
- transaction_date, post_date (temporal)
- direction (CREDIT/DEBIT)
- Derived: day_of_week, day_of_month, month, year, amount_bucket

Output: data/datasets/features_prod.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def extract_features(row: Dict[str, str], bs_mappings: Optional[Dict] = None) -> Dict[str, any]:
    """
    Extract ML features from a transaction row.
    
    Only extracts production-ready features (available in bankstatements.com.au data).
    SubClass and ANZSIC features are EXCLUDED (BASIQ-only).
    
    Features include:
    - Text features: description
    - Numeric features: amount, amount_bucket
    - Temporal features: transaction_date, post_date, day_of_week, day_of_month, month, year
    - Metadata: direction, label_source, split
    - BS fallback: bs_category, bs_fallback_group, bs_fallback_confidence (if available)
    """
    features = {}
    
    # Text features (primary signal for categorization)
    features["description"] = row.get("description", "")
    
    # Numeric features
    try:
        features["amount"] = float(row.get("amount", "0"))
    except ValueError:
        features["amount"] = 0.0
    
    # Amount bucket (for pattern recognition)
    amount_abs = abs(features["amount"])
    if amount_abs < 10:
        features["amount_bucket"] = "micro"
    elif amount_abs < 50:
        features["amount_bucket"] = "small"
    elif amount_abs < 200:
        features["amount_bucket"] = "medium"
    elif amount_abs < 1000:
        features["amount_bucket"] = "large"
    else:
        features["amount_bucket"] = "xlarge"
    
    # Direction (inferred from amount)
    features["direction"] = "debit" if features["amount"] < 0 else "credit"
    
    # Temporal features
    tx_date = row.get("transaction_date", "") or row.get("post_date", "")
    features["transaction_date"] = tx_date
    features["post_date"] = row.get("post_date", "")
    
    if tx_date:
        try:
            dt = datetime.fromisoformat(tx_date.replace("Z", "+00:00"))
            features["month"] = dt.month
            features["day_of_week"] = dt.weekday()  # 0=Monday, 6=Sunday
            features["day_of_month"] = dt.day
            features["year"] = dt.year
        except ValueError:
            features["month"] = 0
            features["day_of_week"] = 0
            features["day_of_month"] = 0
            features["year"] = 0
    else:
        features["month"] = 0
        features["day_of_week"] = 0
        features["day_of_month"] = 0
        features["year"] = 0
    
    # BS category fallback (if available)
    bs_category = row.get("bs_category", "")
    features["bs_category"] = bs_category
    
    if bs_mappings and bs_category and bs_category in bs_mappings:
        mapping = bs_mappings[bs_category]
        features["bs_fallback_group"] = mapping["basiq_group"]
        features["bs_fallback_confidence"] = mapping["confidence"]
    else:
        features["bs_fallback_group"] = ""
        features["bs_fallback_confidence"] = 0.0
    
    # Label (target variable)
    features["label_group_code"] = row.get("label_group_code", "")
    features["label_source"] = row.get("label_source", "")
    
    # Metadata
    features["transaction_id"] = row.get("transaction_id", "")
    features["run_id"] = row.get("run_id", "")
    
    return features


def build_feature_dataset(
    dataset_path: Path,
    output_path: Path,
    bs_mappings_path: Optional[Path] = None,
    split_file: Optional[Path] = None,
) -> None:
    """
    Build feature-rich dataset for ML training.
    
    Args:
        dataset_path: Path to tx_labeled.csv
        output_path: Output path for feature dataset
        bs_mappings_path: Optional path to bs_category_mappings.json
        split_file: Optional path to run_splits.json to add split column
    """
    # Load BS category mappings if provided
    bs_mappings = None
    if bs_mappings_path and bs_mappings_path.exists():
        with bs_mappings_path.open() as f:
            data = json.load(f)
            bs_mappings = data.get("mappings", {})
        print(f"Loaded {len(bs_mappings)} BS category mappings")
    
    # Load split information if provided
    run_to_split = {}
    if split_file and split_file.exists():
        with split_file.open() as f:
            split_data = json.load(f)
            for split_name, run_ids in split_data.get("splits", {}).items():
                for run_id in run_ids:
                    run_to_split[run_id] = split_name
        print(f"Loaded split information for {len(run_to_split)} runs")
    
    # Process dataset
    features_list: List[Dict] = []
    print(f"Extracting features from {dataset_path}...")
    
    with dataset_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = extract_features(row, bs_mappings)
            
            # Add split if available
            if run_to_split:
                features["split"] = run_to_split.get(features["run_id"], "unknown")
            
            features_list.append(features)
    
    # Write feature dataset
    if features_list:
        fieldnames = list(features_list[0].keys())
        with output_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for features in features_list:
                writer.writerow(features)
    
    print(f"Wrote {len(features_list)} feature rows to {output_path}")
    
    # Summary statistics
    if features_list:
        label_counts = {}
        for feat in features_list:
            label = feat["label_group_code"]
            label_counts[label] = label_counts.get(label, 0) + 1
        
        print(f"\nLabel distribution:")
        for label, count in sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {label}: {count}")
        
        if "split" in features_list[0]:
            split_counts = {}
            for feat in features_list:
                split = feat.get("split", "unknown")
                split_counts[split] = split_counts.get(split, 0) + 1
            print(f"\nSplit distribution:")
            for split, count in sorted(split_counts.items()):
                print(f"  {split}: {count}")
        
        # Amount bucket distribution
        bucket_counts = {}
        for feat in features_list:
            bucket = feat.get("amount_bucket", "unknown")
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        print(f"\nAmount bucket distribution:")
        for bucket, count in sorted(bucket_counts.items()):
            print(f"  {bucket}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build production-ready feature dataset for ML training."
    )
    parser.add_argument(
        "--dataset",
        default="data/datasets/tx_labeled.csv",
        help="Path to labeled transaction dataset CSV",
    )
    parser.add_argument(
        "--out",
        default="data/datasets/features_prod.csv",
        help="Output path for feature dataset CSV",
    )
    parser.add_argument(
        "--bs-mappings",
        default="data/datasets/bs_category_mappings.json",
        help="Path to BS category mappings JSON (optional)",
    )
    parser.add_argument(
        "--splits",
        default="data/datasets/run_splits.json",
        help="Path to run splits JSON (optional)",
    )
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    output_path = Path(args.out)
    bs_mappings_path = Path(args.bs_mappings) if args.bs_mappings else None
    splits_path = Path(args.splits) if args.splits else None
    
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    build_feature_dataset(
        dataset_path,
        output_path,
        bs_mappings_path,
        splits_path,
    )


if __name__ == "__main__":
    main()

