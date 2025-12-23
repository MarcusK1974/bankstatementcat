#!/usr/bin/env python3
"""
BS Category Mapper

Learns mappings from bankstatements.com.au categories to BASIQ group codes
by matching transactions between BS data and BASIQ labeled data.

Output: data/datasets/bs_category_mappings.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class BSTransaction:
    """BankStatements.com.au transaction"""
    description: str
    amount: float
    date: datetime
    category: str
    third_party: str
    account_type: str
    raw: Dict


@dataclass
class BasiqTransaction:
    """BASIQ labeled transaction"""
    transaction_id: str
    description: str
    amount: float
    transaction_date: datetime
    basiq_group: str
    label_source: str


@dataclass
class CategoryMapping:
    """BS category → BASIQ group mapping with confidence"""
    bs_category: str
    basiq_group: str
    confidence: float
    matched_count: int
    total_count: int
    sample_matches: List[Dict]
    mapping_source: str  # 'transaction_match', 'semantic', or 'fallback'


def _normalize_description(desc: str) -> str:
    """Normalize description for fuzzy matching"""
    # Lowercase
    desc = desc.lower()
    # Remove special characters, keep alphanumeric and spaces
    desc = re.sub(r'[^a-z0-9\s]', '', desc)
    # Collapse multiple spaces
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()


def _parse_bs_csv(path: Path) -> List[BSTransaction]:
    """Parse bankstatements.com.au CSV file"""
    transactions = []
    
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse amount (remove commas, handle negatives)
                amount_str = row.get('amount', '0').replace(',', '')
                amount = float(amount_str)
                
                # Parse date (YYYY-MM-DD format in BS data)
                date_str = row.get('date', '')
                date = datetime.strptime(date_str, '%Y-%m-%d')
                
                tx = BSTransaction(
                    description=row.get('description', ''),
                    amount=amount,
                    date=date,
                    category=row.get('Category', ''),
                    third_party=row.get('thirdParty', ''),
                    account_type=row.get('accountType', ''),
                    raw=dict(row)
                )
                transactions.append(tx)
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue
    
    return transactions


def _parse_basiq_labeled_csv(path: Path) -> List[BasiqTransaction]:
    """Parse BASIQ labeled transaction dataset"""
    transactions = []
    
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse amount
                amount = float(row.get('amount', '0'))
                
                # Parse transaction date (ISO format with timezone)
                date_str = row.get('transaction_date', '')
                if date_str:
                    # Handle ISO format: 2025-08-18T01:16:55Z
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    continue
                
                tx = BasiqTransaction(
                    transaction_id=row.get('transaction_id', ''),
                    description=row.get('description', ''),
                    amount=amount,
                    transaction_date=date,
                    basiq_group=row.get('label_group_code', ''),
                    label_source=row.get('label_source', '')
                )
                transactions.append(tx)
            except (ValueError, KeyError) as e:
                continue
    
    return transactions


def _fuzzy_match(
    bs_tx: BSTransaction, 
    basiq_tx: BasiqTransaction,
    amount_tolerance: float = 0.01,
    date_tolerance_days: int = 2
) -> bool:
    """Check if two transactions match using fuzzy logic"""
    
    # Amount must match within tolerance
    if abs(bs_tx.amount - basiq_tx.amount) > amount_tolerance:
        return False
    
    # Date must match within tolerance
    date_diff = abs((bs_tx.date - basiq_tx.transaction_date.replace(tzinfo=None)).days)
    if date_diff > date_tolerance_days:
        return False
    
    # Description must have some overlap (fuzzy)
    bs_norm = _normalize_description(bs_tx.description)
    basiq_norm = _normalize_description(basiq_tx.description)
    
    # At least 60% of words in common (simple heuristic)
    bs_words = set(bs_norm.split())
    basiq_words = set(basiq_norm.split())
    
    if not bs_words or not basiq_words:
        return False
    
    overlap = len(bs_words & basiq_words)
    min_words = min(len(bs_words), len(basiq_words))
    
    if min_words == 0:
        return False
    
    overlap_ratio = overlap / min_words
    return overlap_ratio >= 0.4  # At least 40% word overlap


def _get_semantic_mapping(bs_category: str) -> Optional[str]:
    """Get semantic/rule-based mapping for BS category to BASIQ code"""
    # Manually curated mappings based on category name semantics
    # These are educated guesses that should be reasonable fallbacks
    mappings = {
        # Income categories
        'Wages': 'INC-009',
        'Salary': 'INC-009',
        'Other Income': 'INC-007',  # Other Credits
        'All Other Credits': 'INC-007',
        'Earned Interest': 'INC-004',  # Interest Income
        'Interest': 'INC-004',
        'Medicare': 'INC-015',  # Medicare income
        'Benefits': 'INC-001',
        'Centrelink': 'INC-014',
        'Pension': 'INC-018',
        
        # Transfer categories (expense side)
        'Internal Transfer': 'EXP-013',  # Will be overridden by transfer detector
        'External Transfers': 'EXP-013',
        'Transfer': 'EXP-013',
        
        # Expense categories
        'Groceries': 'EXP-016',
        'Supermarket': 'EXP-016',
        'Dining Out': 'EXP-008',
        'Restaurants': 'EXP-008',
        'Utilities': 'EXP-040',
        'Insurance': 'EXP-021',
        'Health': 'EXP-018',  # Medical (not Home Improvement!)
        'Medical': 'EXP-018',
        'Transport': 'EXP-041',  # Vehicle and Transport
        'Fuel': 'EXP-041',
        'Automotive': 'EXP-002',
        'Entertainment': 'EXP-012',
        'Shopping': 'EXP-031',  # Retail
        'Retail': 'EXP-031',
        'Online Retail': 'EXP-024',
        'Online Retail and Subscription Services': 'EXP-035',  # Subscription Media & Software
        'Education': 'EXP-011',  # Education and Childcare
        'Travel': 'EXP-038',
        'Home': 'EXP-019',  # Home Improvement
        'Home Improvement': 'EXP-019',
        'Rent': 'EXP-030',
        'Mortgage': 'EXP-056',  # Mortgage Repayments
        'Mortgage Repayments': 'EXP-056',
        'Loan Repayments': 'EXP-057',
        'Cash': 'EXP-007',  # Department Stores (ATM withdrawals)
        'ATM': 'EXP-001',  # ATM Withdrawals
        'Subscription': 'EXP-035',
        'Subscriptions': 'EXP-035',
        'Fees': 'EXP-015',  # Government & Council Services
        'Bank Fees': 'EXP-015',
        'Tax': 'EXP-015',  # Government & Council Services
        'Government and Council Services': 'EXP-015',
        'Council Rates': 'EXP-015',
        'Charity': 'EXP-010',  # Donations
        'Donations': 'EXP-010',
        'Clothing': 'EXP-055',  # Clothing and Footwear
        'Fashion': 'EXP-055',
        'Sports': 'EXP-052',  # Sports and Hobbies
        'Fitness': 'EXP-017',  # Gyms and memberships
        'Gambling': 'EXP-014',
        'Betting': 'EXP-014',
        'Alcohol': 'EXP-051',  # Alcohol and Tobacco
        'Liquor': 'EXP-051',
        'Tobacco': 'EXP-051',
        'Phone': 'EXP-036',
        'Telecommunications': 'EXP-036',
        'Internet': 'EXP-036',
        'Pet': 'EXP-028',  # Pet Care
        'Pets': 'EXP-028',
        'Pet Care': 'EXP-028',
        'Personal Care': 'EXP-027',
        'Credit Card Repayments': 'EXP-061',
        'Credit Card': 'EXP-061',
    }
    
    # Try exact match
    if bs_category in mappings:
        return mappings[bs_category]
    
    # Try case-insensitive partial match
    bs_lower = bs_category.lower()
    for key, value in mappings.items():
        if key.lower() in bs_lower or bs_lower in key.lower():
            return value
    
    return None


def _build_mappings(
    bs_transactions: List[BSTransaction],
    basiq_transactions: List[BasiqTransaction]
) -> Dict[str, CategoryMapping]:
    """Build BS category → BASIQ group mappings"""
    
    # Group BS transactions by category
    bs_by_category: Dict[str, List[BSTransaction]] = defaultdict(list)
    for tx in bs_transactions:
        if tx.category:
            bs_by_category[tx.category].append(tx)
    
    # Find matches for each category
    mappings = {}
    
    for bs_category, bs_txs in bs_by_category.items():
        # Track which BASIQ groups match for this BS category
        group_matches: Dict[str, List[Dict]] = defaultdict(list)
        
        # Try to find matching BASIQ transactions
        for bs_tx in bs_txs:
            for basiq_tx in basiq_transactions:
                if _fuzzy_match(bs_tx, basiq_tx):
                    match_info = {
                        'bs_description': bs_tx.description,
                        'basiq_description': basiq_tx.description,
                        'amount': bs_tx.amount,
                        'bs_date': bs_tx.date.isoformat(),
                        'basiq_date': basiq_tx.transaction_date.isoformat(),
                        'basiq_group': basiq_tx.basiq_group,
                        'label_source': basiq_tx.label_source
                    }
                    group_matches[basiq_tx.basiq_group].append(match_info)
                    break  # Only match to first BASIQ transaction found
        
        # Determine mapping
        if group_matches:
            # Use matched data (high confidence)
            best_group = max(group_matches.keys(), key=lambda g: len(group_matches[g]))
            matched_count = len(group_matches[best_group])
            total_count = len(bs_txs)
            confidence = matched_count / total_count if total_count > 0 else 0.0
            samples = group_matches[best_group][:3]
            
            mappings[bs_category] = CategoryMapping(
                bs_category=bs_category,
                basiq_group=best_group,
                confidence=confidence,
                matched_count=matched_count,
                total_count=total_count,
                sample_matches=samples,
                mapping_source='transaction_match'
            )
        else:
            # Use semantic mapping (low-medium confidence)
            semantic_group = _get_semantic_mapping(bs_category)
            if semantic_group:
                mappings[bs_category] = CategoryMapping(
                    bs_category=bs_category,
                    basiq_group=semantic_group,
                    confidence=0.5,  # Medium confidence for semantic mapping
                    matched_count=0,
                    total_count=len(bs_txs),
                    sample_matches=[],
                    mapping_source='semantic'
                )
            else:
                # No mapping found - use uncategorized based on amount sign
                # Determine if this is mostly income or expense based on transaction amounts
                avg_amount = sum(tx.amount for tx in bs_txs) / len(bs_txs)
                default_group = 'INC-007' if avg_amount > 0 else 'EXP-039'
                
                mappings[bs_category] = CategoryMapping(
                    bs_category=bs_category,
                    basiq_group=default_group,
                    confidence=0.3,  # Low confidence for fallback
                    matched_count=0,
                    total_count=len(bs_txs),
                    sample_matches=[],
                    mapping_source='fallback'
                )
    
    return mappings


def _save_mappings(mappings: Dict[str, CategoryMapping], output_path: Path) -> None:
    """Save mappings to JSON file"""
    output_data = {
        'mappings': {},
        'metadata': {
            'total_categories': len(mappings),
            'transaction_match': sum(1 for m in mappings.values() if m.mapping_source == 'transaction_match'),
            'semantic': sum(1 for m in mappings.values() if m.mapping_source == 'semantic'),
            'fallback': sum(1 for m in mappings.values() if m.mapping_source == 'fallback'),
            'high_confidence': sum(1 for m in mappings.values() if m.confidence >= 0.8),
            'medium_confidence': sum(1 for m in mappings.values() if 0.5 <= m.confidence < 0.8),
            'low_confidence': sum(1 for m in mappings.values() if m.confidence < 0.5)
        }
    }
    
    for category, mapping in sorted(mappings.items()):
        output_data['mappings'][category] = {
            'basiq_group': mapping.basiq_group,
            'confidence': round(mapping.confidence, 3),
            'matched_count': mapping.matched_count,
            'total_count': mapping.total_count,
            'mapping_source': mapping.mapping_source,
            'sample_matches': mapping.sample_matches
        }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='Build BS category → BASIQ group mappings')
    parser.add_argument(
        '--bs-csv',
        type=Path,
        default=Path('/Users/marcuskorff/Documents/Bank Statements/Marcus/bankstatementsubmissionforreferrercodenqyf/NQYF--anz-7747-v2.csv'),
        help='Path to bankstatements.com.au CSV file'
    )
    parser.add_argument(
        '--basiq-labeled',
        type=Path,
        default=Path('data/datasets/tx_labeled.csv'),
        help='Path to BASIQ labeled transaction dataset'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/datasets/bs_category_mappings.json'),
        help='Output path for mappings JSON'
    )
    
    args = parser.parse_args()
    
    print(f"Loading BS transactions from: {args.bs_csv}")
    bs_transactions = _parse_bs_csv(args.bs_csv)
    print(f"  Loaded {len(bs_transactions)} BS transactions")
    
    # Count categories
    bs_categories = set(tx.category for tx in bs_transactions if tx.category)
    print(f"  Found {len(bs_categories)} unique BS categories")
    
    print(f"\nLoading BASIQ labeled transactions from: {args.basiq_labeled}")
    basiq_transactions = _parse_basiq_labeled_csv(args.basiq_labeled)
    print(f"  Loaded {len(basiq_transactions)} BASIQ transactions")
    
    print("\nMatching BS transactions to BASIQ transactions...")
    mappings = _build_mappings(bs_transactions, basiq_transactions)
    
    print(f"\nBuilt {len(mappings)} category mappings:")
    for category, mapping in sorted(mappings.items(), key=lambda x: x[1].confidence, reverse=True):
        source_label = f"[{mapping.mapping_source}]"
        print(f"  {category:30s} → {mapping.basiq_group}  "
              f"(confidence: {mapping.confidence:.1%}, source: {source_label})")
    
    print(f"\nSaving mappings to: {args.output}")
    _save_mappings(mappings, args.output)
    
    print("\nMapping Source Distribution:")
    tx_match = sum(1 for m in mappings.values() if m.mapping_source == 'transaction_match')
    semantic = sum(1 for m in mappings.values() if m.mapping_source == 'semantic')
    fallback = sum(1 for m in mappings.values() if m.mapping_source == 'fallback')
    print(f"  Transaction Match: {tx_match}")
    print(f"  Semantic:         {semantic}")
    print(f"  Fallback:         {fallback}")
    
    print("\nConfidence Distribution:")
    high = sum(1 for m in mappings.values() if m.confidence >= 0.8)
    medium = sum(1 for m in mappings.values() if 0.5 <= m.confidence < 0.8)
    low = sum(1 for m in mappings.values() if m.confidence < 0.5)
    print(f"  High (≥80%):      {high}")
    print(f"  Medium (50-80%):  {medium}")
    print(f"  Low (<50%):       {low}")
    
    print("\n✓ BS category mappings built successfully")


if __name__ == '__main__':
    main()

