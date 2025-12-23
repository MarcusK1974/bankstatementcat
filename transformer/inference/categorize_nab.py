#!/usr/bin/env python3
"""
NAB Credit Card CSV Parser

Parses NAB credit card transaction CSVs and categorizes them using the hybrid system.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from transformer.inference.predictor_hybrid import HybridTransactionCategorizer
from transformer.inference.normalizer import normalize_description


def parse_nab_csv(csv_path: Path):
    """Parse NAB credit card CSV."""
    transactions = []
    
    with csv_path.open('r', encoding='utf-8') as f:
        # Try to detect the format
        sample = f.read(1024)
        f.seek(0)
        
        reader = csv.DictReader(f)
        
        for row in reader:
            # NAB format can vary, try common column names
            description = (
                row.get('Description') or 
                row.get('description') or 
                row.get('Transaction Details') or
                row.get('Merchant') or
                ''
            )
            
            amount_str = (
                row.get('Amount') or 
                row.get('amount') or 
                row.get('Debit') or 
                row.get('Credit') or
                '0'
            )
            
            # Parse amount (handle different formats)
            amount_str = amount_str.replace('$', '').replace(',', '').strip()
            if amount_str.startswith('(') and amount_str.endswith(')'):
                # Negative in parentheses
                amount_str = '-' + amount_str[1:-1]
            
            try:
                amount = float(amount_str)
            except ValueError:
                continue
            
            # Parse date
            date_str = row.get('Date') or row.get('date') or row.get('Transaction Date') or ''
            
            transactions.append({
                'description': description,
                'amount': amount,
                'date': date_str,
                'raw_row': row
            })
    
    return transactions


def categorize_nab_transactions(
    csv_path: Path,
    output_path: Path,
    use_claude: bool = True
):
    """Categorize NAB credit card transactions."""
    
    print(f"Loading NAB credit card transactions from: {csv_path}")
    transactions = parse_nab_csv(csv_path)
    print(f"Loaded {len(transactions)} transactions")
    
    if not transactions:
        print("No transactions found. Please check the CSV format.")
        return
    
    # Show sample for verification
    print("\nSample transactions:")
    for tx in transactions[:3]:
        print(f"  {tx['description'][:50]:50s} ${tx['amount']:>10.2f}")
    
    # Initialize categorizer (without BERT model requirement)
    print("\nInitializing hybrid categorizer (no BERT model needed)...")
    
    import os
    os.environ['ANTHROPIC_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY', '')
    
    categorizer = HybridTransactionCategorizer(
        model_dir=Path('models/bert_transaction_categorizer_v3'),
        bs_mappings_path=Path('data/datasets/bs_category_mappings.json'),
        basiq_groups_path=Path('docs/basiq_groups.yaml'),
        learned_patterns_path=Path('data/learned_patterns.json'),
        enable_transfer_detection=True,
        enable_learning=True,
        enable_claude=use_claude,
        test_mode=(not use_claude)
    )
    
    # Categorize
    print("\nCategorizing transactions...")
    results = []
    
    for tx in transactions:
        category, confidence, source = categorizer.predict(
            description=tx['description'],
            amount=tx['amount'],
            bs_category=None,  # NAB doesn't provide category
        )
        
        results.append({
            'date': tx['date'],
            'description': tx['description'],
            'amount': tx['amount'],
            'normalized': normalize_description(tx['description']),
            'predicted_category': category,
            'confidence': confidence,
            'source': source,
        })
    
    # Save results
    print(f"\nSaving results to: {output_path}")
    with output_path.open('w', newline='', encoding='utf-8') as f:
        if results:
            fieldnames = list(results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
    
    # Statistics
    from collections import Counter
    sources = Counter(r['source'] for r in results)
    categories = Counter(r['predicted_category'] for r in results)
    
    print(f"\n✓ Categorized {len(results)} transactions")
    
    print("\nPrediction Source Breakdown:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / len(results)
        print(f"  {source:20s}: {count:4d} ({pct:5.1f}%)")
    
    print("\nTop 10 Categories:")
    for cat, count in categories.most_common(10):
        pct = 100 * count / len(results)
        print(f"  {cat}: {count:4d} ({pct:5.1f}%)")
    
    # Show sample categorizations
    print("\nSample Categorizations:")
    print(f"  {'Description':<50} {'Amount':>10} {'Category':<10} {'Source':<15}")
    print("  " + "-" * 95)
    for r in results[:10]:
        desc = r['description'][:47] + '...' if len(r['description']) > 50 else r['description']
        print(f"  {desc:<50} ${r['amount']:>9.2f} {r['predicted_category']:<10} {r['source']:<15}")
    
    # Save learned patterns if any were learned
    if categorizer.learned_patterns:
        categorizer.save_learned_patterns()
        stats = categorizer.learned_patterns.get_statistics()
        print(f"\nLearned Patterns: {stats['total_patterns']} total")
    
    print(f"\n✓ Results saved to: {output_path}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Categorize NAB credit card transactions')
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to NAB credit card CSV file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/output/nab_categorized.csv'),
        help='Output CSV path'
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Run in test mode (no Claude API calls)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    categorize_nab_transactions(
        csv_path=args.input,
        output_path=args.output,
        use_claude=(not args.test_mode)
    )

