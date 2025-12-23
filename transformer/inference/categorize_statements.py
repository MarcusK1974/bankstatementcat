#!/usr/bin/env python3
"""
Categorize personal bank statements using trained BERT model
WITH full BASIQ category descriptions
"""

import csv
import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from inference.predictor import TransactionCategorizer


def load_basiq_descriptions(groups_path: Path) -> dict:
    """Load BASIQ group code descriptions from YAML"""
    with groups_path.open('r') as f:
        data = yaml.safe_load(f)
    
    descriptions = {}
    for group in data.get('groups', []):
        code = group.get('code')
        # Try both 'name' and 'title' fields
        desc = group.get('name') or group.get('title', '')
        descriptions[code] = desc
    
    return descriptions


def categorize_bank_statements(
    bs_csv_path: Path,
    model_dir: Path,
    bs_mappings_path: Path,
    groups_path: Path,
    output_path: Path
):
    """Categorize bank statements and output to CSV with descriptions"""
    
    # Load BASIQ descriptions
    print(f"Loading BASIQ category descriptions from {groups_path}...")
    basiq_descriptions = load_basiq_descriptions(groups_path)
    print(f"Loaded {len(basiq_descriptions)} category descriptions")
    
    # Initialize categorizer with 4-tier pipeline
    print(f"\nLoading model from {model_dir}...")
    categorizer = TransactionCategorizer(
        model_dir=model_dir,
        bs_mappings_path=bs_mappings_path,
        basiq_groups_path=groups_path,
        bert_confidence_threshold=0.8,
        llm_confidence_threshold=0.9,
        enable_transfer_detection=True,
        enable_llm=True
    )
    
    # Load bank statements
    print(f"\nLoading bank statements from {bs_csv_path}...")
    transactions = []
    with bs_csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                'date': row.get('date', ''),
                'description': row.get('description', ''),
                'amount': float(row.get('amount', '0').replace(',', '')),
                'balance': row.get('Balance', ''),
                'bs_category': row.get('Category', ''),
                'third_party': row.get('thirdParty', ''),
                'account_type': row.get('accountType', ''),
                'account_number': row.get('accountNumber', ''),
                'bsb': row.get('bsb', ''),
            })
    
    print(f"Loaded {len(transactions)} transactions")
    
    # Train transfer detector on all transactions
    if categorizer.enable_transfer_detection:
        categorizer.train_transfer_detector(transactions)
    
    # Categorize
    print("\nCategorizing transactions...")
    results = []
    for tx in transactions:
        pred, conf, source = categorizer.predict(
            description=tx['description'],
            amount=tx['amount'],
            bs_category=tx['bs_category'],
            third_party=tx['third_party'],
            account_number=tx['account_number'],
            bsb=tx['bsb']
        )
        
        # Get full description
        basiq_description = basiq_descriptions.get(pred, 'Unknown category')
        
        results.append({
            'date': tx['date'],
            'description': tx['description'],
            'amount': tx['amount'],
            'balance': tx['balance'],
            'bs_category': tx['bs_category'],
            'basiq_category_code': pred,
            'basiq_category_description': basiq_description,
            'confidence': round(conf, 3),
            'prediction_source': source,
            'account_type': tx['account_type'],
        })
    
    # Write output
    print(f"\nWriting results to {output_path}...")
    with output_path.open('w', newline='', encoding='utf-8') as f:
        if results:
            fieldnames = list(results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
    
    # Print summary
    print(f"\n✓ Categorized {len(results)} transactions")
    
    # Count by source
    source_counts = {}
    for r in results:
        source = r['prediction_source']
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print("\nPrediction Source Breakdown:")
    for source, count in sorted(source_counts.items()):
        pct = 100 * count / len(results)
        print(f"  {source:15s}: {count:4d} ({pct:5.1f}%)")
    
    # Count by category
    category_counts = {}
    for r in results:
        cat = r['basiq_category_code']
        desc = r['basiq_category_description']
        category_counts[cat] = (category_counts.get(cat, [0, ''])[0] + 1, desc)
    
    print("\nTop 10 BASIQ Categories:")
    for cat, (count, desc) in sorted(category_counts.items(), key=lambda x: x[1][0], reverse=True)[:10]:
        pct = 100 * count / len(results)
        print(f"  {cat} - {desc}: {count:4d} ({pct:5.1f}%)")
    
    print(f"\n✓ Results saved to: {output_path}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Categorize personal bank statements with descriptions')
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('/Users/marcuskorff/Documents/Bank Statements/Marcus/bankstatementsubmissionforreferrercodenqyf/NQYF--anz-7747-v2.csv'),
        help='Input bank statement CSV'
    )
    parser.add_argument(
        '--model',
        type=Path,
        default=Path('models/bert_transaction_categorizer_v3'),
        help='Model directory'
    )
    parser.add_argument(
        '--bs-mappings',
        type=Path,
        default=Path('data/datasets/bs_category_mappings.json'),
        help='BS category mappings'
    )
    parser.add_argument(
        '--groups',
        type=Path,
        default=Path('docs/basiq_groups.yaml'),
        help='BASIQ groups YAML with descriptions'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/output/marcus_statements_categorized.csv'),
        help='Output CSV path'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    categorize_bank_statements(
        bs_csv_path=args.input,
        model_dir=args.model,
        bs_mappings_path=args.bs_mappings,
        groups_path=args.groups,
        output_path=args.output
    )
