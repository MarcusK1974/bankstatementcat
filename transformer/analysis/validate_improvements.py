#!/usr/bin/env python3
"""
Validation Report for Categorization Improvements
"""

import csv
from collections import Counter
from pathlib import Path


def main():
    print('='*80)
    print('CATEGORIZATION IMPROVEMENTS VALIDATION')
    print('='*80)
    print()
    
    # Load categorized data
    csv_path = Path('data/output/marcus_statements_categorized.csv')
    with csv_path.open('r') as f:
        reader = csv.DictReader(f)
        transactions = list(reader)
    
    # Test cases from user's observations
    test_cases = [
        {
            'pattern': 'MOMENTUM ENERGY',
            'expected_code': 'EXP-040',
            'expected_name': 'Utilities',
            'issue': 'Was Motor Finance (EXP-023)'
        },
        {
            'pattern': 'TAX OFFICE',
            'expected_code': 'EXP-015',
            'expected_name': 'Government & Council Services',
            'issue': 'Was Uncategorised (EXP-039)'
        },
        {
            'pattern': 'NAB CARDS',
            'expected_code': 'EXP-061',
            'expected_name': 'Credit Card Repayments',
            'issue': 'Was Uncategorised (EXP-039)'
        },
        {
            'pattern': 'MCARE BENEFITS',
            'expected_code': 'INC-015',
            'expected_name': 'Medicare',
            'issue': 'Was Home Improvement (EXP-019)'
        }
    ]
    
    print('TEST CASES (User-reported Issues):')
    print('-'*80)
    for i, test in enumerate(test_cases, 1):
        print(f'{i}. {test["pattern"]}')
        print(f'   Expected: {test["expected_code"]} - {test["expected_name"]}')
        print(f'   Previous Issue: {test["issue"]}')
        
        # Find matching transactions
        matches = [tx for tx in transactions if test['pattern'] in tx['description'].upper()]
        
        if matches:
            correct = sum(1 for tx in matches if tx['basiq_category_code'] == test['expected_code'])
            status = '✓' if correct == len(matches) else '⚠'
            print(f'   Result: {correct}/{len(matches)} correctly categorized {status}')
            
            # Show first match details
            first = matches[0]
            desc = first["description"][:50] + '...' if len(first["description"]) > 50 else first["description"]
            print(f'   Example: "{desc}"')
            print(f'            → {first["basiq_category_code"]} ({first["prediction_source"]}, conf: {first["confidence"]})')
        else:
            print(f'   Result: No matching transactions found')
        print()
    
    # Internal transfer detection
    print('INTERNAL TRANSFER DETECTION:')
    print('-'*80)
    internal_transfers = [tx for tx in transactions if tx['prediction_source'] == 'internal_transfer']
    print(f'Total internal transfers detected: {len(internal_transfers)}')
    
    # Show sample
    print('\nSample internal transfers:')
    for tx in internal_transfers[:5]:
        desc = tx["description"][:60]
        amt = float(tx["amount"])
        print(f'  - {desc:60s} ${amt:>10.2f}')
    print()
    
    # Prediction source breakdown
    print('PREDICTION SOURCE BREAKDOWN:')
    print('-'*80)
    sources = Counter(tx['prediction_source'] for tx in transactions)
    total = len(transactions)
    
    for source, count in sources.most_common():
        pct = 100 * count / total
        print(f'{source:20s}: {count:4d} ({pct:5.1f}%)')
    print()
    
    # Category distribution
    print('TOP 15 CATEGORIES:')
    print('-'*80)
    categories = Counter((tx['basiq_category_code'], tx['basiq_category_description']) for tx in transactions)
    
    for (code, desc), count in categories.most_common(15):
        pct = 100 * count / total
        print(f'{code} {desc:40s}: {count:4d} ({pct:5.1f}%)')
    print()
    
    print('='*80)
    print('✓ VALIDATION COMPLETE')
    print('='*80)


if __name__ == '__main__':
    main()

