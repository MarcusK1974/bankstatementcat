#!/usr/bin/env python3
"""
Compare BERT vs No-BERT performance on NAB credit card data
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Set API key from environment
if 'ANTHROPIC_API_KEY' not in os.environ:
    print("Warning: ANTHROPIC_API_KEY not set. Set it before running.")
    print("export ANTHROPIC_API_KEY='your-key-here'")
    # sys.exit(1)  # Uncomment to exit if key not set

from transformer.inference.predictor import TransactionCategorizer  # Old predictor with BERT
from transformer.inference.predictor_hybrid import HybridTransactionCategorizer  # New hybrid
from transformer.inference.normalizer import normalize_description


def load_nab_csv(csv_path):
    """Load NAB credit card transactions."""
    transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                'date': row.get('date', ''),
                'description': row.get('description', ''),
                'amount': float(row.get('amount', '0').replace(',', '')),
                'category': row.get('Category', ''),  # NAB's own category
            })
    
    return transactions


print("="*80)
print("NAB CREDIT CARD CATEGORIZATION COMPARISON")
print("="*80)
print(f"\nLoading NAB transactions from: cardmok.csv")

transactions = load_nab_csv('cardmok.csv')
print(f"Loaded {len(transactions)} transactions")

# Show sample
print("\nSample transactions:")
for tx in transactions[:5]:
    print(f"  {tx['description'][:50]:50s} ${tx['amount']:>10.2f} (NAB: {tx['category']})")

# =============================================================================
# TEST 1: WITH BERT MODEL (Full System)
# =============================================================================
print("\n" + "="*80)
print("TEST 1: WITH BERT MODEL (Full 5-Tier System)")
print("="*80)

try:
    categorizer_bert = TransactionCategorizer(
        model_dir=Path('models/bert_transaction_categorizer_v3'),
        bs_mappings_path=Path('data/datasets/bs_category_mappings.json'),
        basiq_groups_path=Path('docs/basiq_groups.yaml'),
        bert_confidence_threshold=0.95,
        llm_confidence_threshold=0.95,
        enable_transfer_detection=True,
        enable_llm=True
    )
    
    # Train transfer detector
    categorizer_bert.train_transfer_detector(transactions)
    
    results_bert = []
    print("\nCategorizing...")
    for i, tx in enumerate(transactions):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(transactions)}")
        
        category, confidence, source = categorizer_bert.predict(
            description=tx['description'],
            amount=tx['amount'],
            bs_category=tx['category']
        )
        
        results_bert.append({
            **tx,
            'predicted_category': category,
            'confidence': confidence,
            'source': source,
        })
    
    # Save results
    output_bert = Path('data/output/nab_with_bert.csv')
    with open(output_bert, 'w', newline='', encoding='utf-8') as f:
        fieldnames = list(results_bert[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results_bert:
            writer.writerow(row)
    
    # Statistics
    sources_bert = Counter(r['source'] for r in results_bert)
    categories_bert = Counter(r['predicted_category'] for r in results_bert)
    
    print(f"\n✓ WITH BERT: Categorized {len(results_bert)} transactions")
    print(f"  Output: {output_bert}")
    
    print("\n  Prediction Sources:")
    for source, count in sorted(sources_bert.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / len(results_bert)
        print(f"    {source:20s}: {count:4d} ({pct:5.1f}%)")
    
    print("\n  Top 10 Categories:")
    for cat, count in categories_bert.most_common(10):
        pct = 100 * count / len(results_bert)
        print(f"    {cat}: {count:4d} ({pct:5.1f}%)")

except Exception as e:
    print(f"\n❌ Error with BERT model: {e}")
    results_bert = None

# =============================================================================
# TEST 2: WITHOUT BERT MODEL (Production Mode)
# =============================================================================
print("\n" + "="*80)
print("TEST 2: WITHOUT BERT MODEL (Production/Lightweight Mode)")
print("="*80)

try:
    categorizer_no_bert = HybridTransactionCategorizer(
        model_dir=Path('models/bert_transaction_categorizer_v3'),  # Won't actually load it
        bs_mappings_path=Path('data/datasets/bs_category_mappings.json'),
        basiq_groups_path=Path('docs/basiq_groups.yaml'),
        learned_patterns_path=Path('data/learned_patterns.json'),
        bert_confidence_threshold=0.95,
        rule_confidence_threshold=0.95,
        enable_transfer_detection=True,
        enable_learning=True,
        enable_claude=True,  # Uses Claude instead of BERT
        test_mode=False
    )
    
    # Train transfer detector
    categorizer_no_bert.train_transfer_detector(transactions)
    
    results_no_bert = []
    print("\nCategorizing...")
    for i, tx in enumerate(transactions):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(transactions)}")
        
        category, confidence, source = categorizer_no_bert.predict(
            description=tx['description'],
            amount=tx['amount'],
            bs_category=tx['category']
        )
        
        results_no_bert.append({
            **tx,
            'predicted_category': category,
            'confidence': confidence,
            'source': source,
        })
    
    # Save results
    output_no_bert = Path('data/output/nab_without_bert.csv')
    with open(output_no_bert, 'w', newline='', encoding='utf-8') as f:
        fieldnames = list(results_no_bert[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results_no_bert:
            writer.writerow(row)
    
    # Save learned patterns
    categorizer_no_bert.save_learned_patterns()
    
    # Statistics
    sources_no_bert = Counter(r['source'] for r in results_no_bert)
    categories_no_bert = Counter(r['predicted_category'] for r in results_no_bert)
    
    print(f"\n✓ WITHOUT BERT: Categorized {len(results_no_bert)} transactions")
    print(f"  Output: {output_no_bert}")
    
    print("\n  Prediction Sources:")
    for source, count in sorted(sources_no_bert.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / len(results_no_bert)
        print(f"    {source:20s}: {count:4d} ({pct:5.1f}%)")
    
    print("\n  Top 10 Categories:")
    for cat, count in categories_no_bert.most_common(10):
        pct = 100 * count / len(results_no_bert)
        print(f"    {cat}: {count:4d} ({pct:5.1f}%)")
    
    # Show learning stats
    if categorizer_no_bert.learned_patterns:
        stats = categorizer_no_bert.learned_patterns.get_statistics()
        print(f"\n  Learned Patterns: {stats['total_patterns']} total")
        print(f"  Claude Calls Saved: {stats.get('claude_calls_saved', 0)}")

except Exception as e:
    print(f"\n❌ Error without BERT: {e}")
    import traceback
    traceback.print_exc()
    results_no_bert = None

# =============================================================================
# COMPARISON
# =============================================================================
if results_bert and results_no_bert:
    print("\n" + "="*80)
    print("COMPARISON: WITH BERT vs WITHOUT BERT")
    print("="*80)
    
    # Compare sources
    print("\nPrediction Source Comparison:")
    all_sources = set(sources_bert.keys()) | set(sources_no_bert.keys())
    print(f"  {'Source':<20} {'With BERT':>15} {'Without BERT':>15} {'Difference':>15}")
    print("  " + "-"*70)
    for source in sorted(all_sources):
        count_bert = sources_bert.get(source, 0)
        count_no_bert = sources_no_bert.get(source, 0)
        diff = count_no_bert - count_bert
        pct_bert = 100 * count_bert / len(results_bert)
        pct_no_bert = 100 * count_no_bert / len(results_no_bert)
        print(f"  {source:<20} {count_bert:6d} ({pct_bert:5.1f}%) {count_no_bert:6d} ({pct_no_bert:5.1f}%) {diff:+6d}")
    
    # Agreement rate
    agreements = sum(1 for rb, rnb in zip(results_bert, results_no_bert) 
                    if rb['predicted_category'] == rnb['predicted_category'])
    agreement_rate = 100 * agreements / len(results_bert)
    
    print(f"\nAgreement Rate: {agreements}/{len(results_bert)} ({agreement_rate:.1f}%)")
    print(f"Disagreements: {len(results_bert) - agreements} transactions")
    
    # Show sample disagreements
    print("\nSample Disagreements (first 5):")
    print(f"  {'Description':<40} {'With BERT':<12} {'Without BERT':<12}")
    print("  " + "-"*70)
    disagreements = [(rb, rnb) for rb, rnb in zip(results_bert, results_no_bert) 
                     if rb['predicted_category'] != rnb['predicted_category']]
    for rb, rnb in disagreements[:5]:
        desc = rb['description'][:37] + '...' if len(rb['description']) > 40 else rb['description']
        print(f"  {desc:<40} {rb['predicted_category']:<12} {rnb['predicted_category']:<12}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
print("\nOutput Files:")
print("  WITH BERT:    data/output/nab_with_bert.csv")
print("  WITHOUT BERT: data/output/nab_without_bert.csv")

