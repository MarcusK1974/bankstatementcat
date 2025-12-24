#!/usr/bin/env python3
"""
Final Simplified Transaction Categorizer

4-Step Categorization Flow:
1. Normalize Description (strip transaction types)
2. Check Internal Transfer
3. Check Comprehensive Brand Database (96-98% coverage, FREE)
4. Claude Validates BS Category or Categorizes (2-4% of transactions)

This represents the production-ready system with maximum cost efficiency.
"""

import os
import sys
from typing import Dict, Optional, Tuple
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from transformer.config.australian_brands_comprehensive import get_category
from transformer.inference.transaction_normalizer import normalize_description
from transformer.inference.transfer_detector import InternalTransferDetector
from transformer.inference.claude_categorizer import ClaudeCategorizer
import json


class FinalTransactionCategorizer:
    """
    Production-ready transaction categorizer with maximum efficiency.
    
    Uses comprehensive brand database (711 rules) for 96-98% of transactions,
    falling back to Claude only for edge cases.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        db_confidence_threshold: float = 0.90,
        enable_learning: bool = True,
        test_mode: bool = False
    ):
        """
        Initialize the final categorizer.
        
        Args:
            api_key: Claude API key (optional - only needed for 2-4% of transactions)
            db_confidence_threshold: Minimum confidence to use DB result (default 0.90)
            enable_learning: Enable Claude learning for continuous improvement
            test_mode: Test mode (disables learning)
        """
        self.db_threshold = db_confidence_threshold
        self.transfer_detector = InternalTransferDetector()
        
        # Load BS category mappings from JSON
        self.bs_mappings = {}
        bs_mappings_path = project_root / 'data' / 'datasets' / 'bs_category_mappings.json'
        if bs_mappings_path.exists():
            with open(bs_mappings_path, 'r') as f:
                data = json.load(f)
                # Structure: {"mappings": {"Category Name": {"basiq_group": "...", "confidence": ...}}}
                if 'mappings' in data:
                    self.bs_mappings = {
                        category: (info['basiq_group'], info['confidence'])
                        for category, info in data['mappings'].items()
                    }
                else:
                    # Alternative format: list of items
                    self.bs_mappings = {
                        item['bs_category']: (item['basiq_group'], item['confidence'])
                        for item in data
                    }
        
        # Initialize Claude (only if API key provided)
        self.claude = None
        if api_key:
            try:
                self.claude = ClaudeCategorizer(api_key)
                self.enable_learning = enable_learning and not test_mode
            except Exception as e:
                print(f"Warning: Claude initialization failed: {e}")
                print("Will fall back to BS categories for uncategorized transactions")
        
        # Statistics
        self.stats = {
            'total': 0,
            'internal_transfer': 0,
            'comprehensive_db_high_conf': 0,  # ≥0.90
            'comprehensive_db_medium_conf': 0,  # 0.80-0.89
            'comprehensive_db_low_conf': 0,  # <0.80
            'claude_validation': 0,
            'claude_categorization': 0,
            'bs_fallback': 0,
            'uncategorized': 0,
        }
    
    def categorize(self, transaction: Dict) -> Tuple[str, float, str]:
        """
        Categorize a transaction using the 4-step flow.
        
        Args:
            transaction: Transaction dict with keys:
                - description: Raw transaction description
                - amount: Transaction amount
                - bs_category: Category from bankstatements.com.au (optional)
                - account_number: Account number (optional, for transfer detection)
                
        Returns:
            Tuple of (basiq_category, confidence, source)
        """
        self.stats['total'] += 1
        
        # Step 1: Normalize Description
        raw_description = transaction.get('description', '')
        normalized, tx_type = normalize_description(raw_description)
        
        # Step 2: Check Internal Transfer
        is_internal = self.transfer_detector.is_internal_transfer(
            description=normalized,
            amount=transaction.get('amount', 0),
            bs_category=transaction.get('bs_category'),
            third_party=transaction.get('third_party')
        )
        
        if is_internal:
            self.stats['internal_transfer'] += 1
            return 'INTERNAL_TRANSFER', 1.0, 'internal_transfer'
        
        # Step 3: Check Comprehensive Brand Database
        db_category, db_confidence, db_reason = get_category(normalized)
        
        if db_category:
            # High confidence - use directly
            if db_confidence >= self.db_threshold:
                self.stats['comprehensive_db_high_conf'] += 1
                return db_category, db_confidence, f'comprehensive_db:{db_reason}'
            
            # Medium confidence - might validate with Claude if available
            elif db_confidence >= 0.80:
                self.stats['comprehensive_db_medium_conf'] += 1
                
                # If Claude available, validate against BS category
                bs_category = transaction.get('bs_category')
                if self.claude and bs_category:
                    return self._validate_with_claude(
                        normalized, transaction, bs_category, 
                        db_suggestion=(db_category, db_confidence, db_reason)
                    )
                
                # Otherwise, use DB result
                return db_category, db_confidence, f'comprehensive_db:{db_reason}'
            
            # Low confidence - prefer Claude or BS fallback
            else:
                self.stats['comprehensive_db_low_conf'] += 1
                # Continue to Step 4
        
        # Step 4: Check BS Category - Use if Clear, Claude if Vague
        bs_category = transaction.get('bs_category')
        
        if bs_category:
            # Define vague/unmappable BS categories that need Claude to learn
            VAGUE_BS_CATEGORIES = {
                'Third Party Payment Providers',  # Too generic - need to learn actual merchant
                'Uncategorised',                   # Unknown - need to learn
                'Department Stores',               # Too broad - better to learn specific store
                'Financial Services',              # Too broad
                'Overdrawn',                       # Not a spending category
            }
            
            # If BS category is vague/unmappable, invoke Claude to learn what it actually is
            if bs_category in VAGUE_BS_CATEGORIES:
                if self.claude:
                    self.stats['claude_categorization'] += 1
                    return self._categorize_with_claude(normalized, transaction)
                else:
                    # No Claude - have to fall back to uncategorized
                    self.stats['uncategorized'] += 1
                    amount = transaction.get('amount', 0)
                    if amount < 0:
                        return 'EXP-039', 0.3, 'uncategorized_fallback'
                    else:
                        return 'INC-007', 0.3, 'uncategorized_fallback'
            
            # BS category is clear and mappable - use it directly
            if bs_category in self.bs_mappings:
                self.stats['bs_fallback'] += 1
                mapped_category, mapped_conf = self.bs_mappings[bs_category]
                return mapped_category, mapped_conf, 'bs_fallback'
        
        # No BS category at all - try Claude or fall back to uncategorized
        if self.claude:
            self.stats['claude_categorization'] += 1
            return self._categorize_with_claude(normalized, transaction)
        
        # Last resort - uncategorized
        self.stats['uncategorized'] += 1
        amount = transaction.get('amount', 0)
        if amount < 0:
            return 'EXP-039', 0.3, 'uncategorized_fallback'
        else:
            return 'INC-007', 0.3, 'uncategorized_fallback'
    
    def _validate_with_claude(
        self, 
        normalized_desc: str,
        transaction: Dict, 
        bs_category: str,
        db_suggestion: Optional[Tuple[str, float, str]] = None
    ) -> Tuple[str, float, str]:
        """
        Use Claude to validate a BS category for reasonableness.
        
        Args:
            normalized_desc: Normalized transaction description
            transaction: Full transaction dict (for amount, etc.)
            bs_category: Category from bankstatements.com.au
            db_suggestion: Optional suggestion from comprehensive DB
            
        Returns:
            Tuple of (basiq_category, confidence, source)
        """
        self.stats['claude_validation'] += 1
        
        # Build validation prompt
        prompt_parts = [
            f"Transaction: {normalized_desc}",
            f"bankstatements.com.au says: {bs_category}",
        ]
        
        if db_suggestion:
            db_cat, db_conf, db_reason = db_suggestion
            prompt_parts.append(f"Our database suggests: {db_cat} ({db_reason}, confidence {db_conf:.2f})")
        
        prompt_parts.append("\nIs the bankstatements.com.au categorization reasonable? If yes, map it to the correct BASIQ category. If no, provide the correct BASIQ category.")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            result = self.claude.predict(normalized_desc, transaction.get('amount', 0), bs_category)
            if result:
                category, confidence, reasoning = result
                return category, confidence, f'claude_validation:{reasoning}'
        except Exception as e:
            print(f"Claude validation failed: {e}")
        
        # Fallback to DB suggestion or BS mapping
        if db_suggestion:
            db_cat, db_conf, db_reason = db_suggestion
            return db_cat, db_conf, f'comprehensive_db_fallback:{db_reason}'
        
        if bs_category in self.bs_mappings:
            mapped_category, mapped_conf = self.bs_mappings[bs_category]
            return mapped_category, mapped_conf, 'bs_fallback'
        
        return 'EXP-039', 0.3, 'uncategorized_fallback'
    
    def _categorize_with_claude(self, normalized_desc: str, transaction: Dict) -> Tuple[str, float, str]:
        """
        Use Claude to categorize a transaction directly.
        
        Args:
            normalized_desc: Normalized transaction description
            transaction: Full transaction dict (for amount, etc.)
            
        Returns:
            Tuple of (basiq_category, confidence, source)
        """
        try:
            result = self.claude.predict(normalized_desc, transaction.get('amount', 0))  # No BS category
            if result:
                category, confidence, reasoning = result
                return category, confidence, f'claude:{reasoning}'
        except Exception as e:
            print(f"Claude categorization failed: {e}")
        
        # Ultimate fallback
        return 'EXP-039', 0.3, 'uncategorized_fallback'
    
    def get_statistics(self) -> Dict:
        """Get categorization statistics."""
        if self.stats['total'] == 0:
            return self.stats
        
        # Calculate percentages
        total = self.stats['total']
        stats_with_pct = self.stats.copy()
        
        for key in ['internal_transfer', 'comprehensive_db_high_conf', 
                    'comprehensive_db_medium_conf', 'comprehensive_db_low_conf',
                    'claude_validation', 'claude_categorization', 
                    'bs_fallback', 'uncategorized']:
            count = self.stats[key]
            pct = (count / total * 100) if total > 0 else 0
            stats_with_pct[f'{key}_pct'] = pct
        
        # Calculate total DB coverage
        db_total = (self.stats['comprehensive_db_high_conf'] + 
                   self.stats['comprehensive_db_medium_conf'] + 
                   self.stats['comprehensive_db_low_conf'])
        stats_with_pct['comprehensive_db_total'] = db_total
        stats_with_pct['comprehensive_db_total_pct'] = (db_total / total * 100) if total > 0 else 0
        
        # Calculate free categorization (no Claude calls)
        free_total = self.stats['internal_transfer'] + db_total + self.stats['bs_fallback']
        stats_with_pct['free_categorization'] = free_total
        stats_with_pct['free_categorization_pct'] = (free_total / total * 100) if total > 0 else 0
        
        # Calculate Claude usage (costs money)
        claude_total = self.stats['claude_validation'] + self.stats['claude_categorization']
        stats_with_pct['claude_total'] = claude_total
        stats_with_pct['claude_total_pct'] = (claude_total / total * 100) if total > 0 else 0
        
        return stats_with_pct
    
    def get_stats(self) -> Dict:
        """Alias for get_statistics() for compatibility."""
        stats = self.get_statistics()
        # Return in the format expected by the calling code
        return {
            'total': stats['total'],
            'internal_transfers': stats['internal_transfer'],
            'comprehensive_db_high': stats['comprehensive_db_high_conf'],
            'comprehensive_db_medium': stats['comprehensive_db_medium_conf'],
            'comprehensive_db_low': stats['comprehensive_db_low_conf'],
            'claude_validation': stats['claude_validation'],
            'claude_categorization': stats['claude_categorization'],
            'bs_fallback': stats['bs_fallback'],
            'uncategorized': stats['uncategorized'],
        }
    
    def print_statistics(self):
        """Print categorization statistics."""
        stats = self.get_statistics()
        
        print("\n" + "=" * 80)
        print("FINAL CATEGORIZER STATISTICS")
        print("=" * 80)
        print(f"\nTotal transactions: {stats['total']}")
        print(f"\n{'Category':<35} {'Count':>8} {'Percentage':>12}")
        print("-" * 80)
        
        # Free categorization (no API costs)
        print(f"{'Internal Transfers':<35} {stats['internal_transfer']:>8} {stats['internal_transfer_pct']:>11.1f}%")
        print(f"{'Comprehensive DB (≥0.90 conf)':<35} {stats['comprehensive_db_high_conf']:>8} {stats['comprehensive_db_high_conf_pct']:>11.1f}%")
        print(f"{'Comprehensive DB (0.80-0.89 conf)':<35} {stats['comprehensive_db_medium_conf']:>8} {stats['comprehensive_db_medium_conf_pct']:>11.1f}%")
        print(f"{'Comprehensive DB (<0.80 conf)':<35} {stats['comprehensive_db_low_conf']:>8} {stats['comprehensive_db_low_conf_pct']:>11.1f}%")
        print(f"{'BS Fallback':<35} {stats['bs_fallback']:>8} {stats['bs_fallback_pct']:>11.1f}%")
        print(f"{'--- TOTAL FREE ---':<35} {stats['free_categorization']:>8} {stats['free_categorization_pct']:>11.1f}%")
        
        # Paid categorization (API costs)
        print(f"\n{'Claude Validation':<35} {stats['claude_validation']:>8} {stats['claude_validation_pct']:>11.1f}%")
        print(f"{'Claude Categorization':<35} {stats['claude_categorization']:>8} {stats['claude_categorization_pct']:>11.1f}%")
        print(f"{'--- TOTAL PAID (CLAUDE) ---':<35} {stats['claude_total']:>8} {stats['claude_total_pct']:>11.1f}%")
        
        # Uncategorized
        print(f"\n{'Uncategorized':<35} {stats['uncategorized']:>8} {stats['uncategorized_pct']:>11.1f}%")
        
        print("=" * 80)
        
        # Cost estimate
        if stats['claude_total'] > 0:
            # Rough estimate: 2000 tokens average per Claude call
            tokens_per_call = 2000
            total_tokens = stats['claude_total'] * tokens_per_call
            cost_per_million = 3.0  # Haiku: $0.25 in + $1.25 out, average $3/M
            estimated_cost = (total_tokens / 1_000_000) * cost_per_million
            
            print(f"\nEstimated Claude API cost for this batch: ${estimated_cost:.4f}")
            print(f"(Based on {stats['claude_total']} calls × ~2K tokens × $3/M tokens)")


if __name__ == '__main__':
    # Test the categorizer
    from transformer.config import api_config
    
    config = api_config.Config()
    
    categorizer = FinalTransactionCategorizer(
        api_key=config.anthropic_api_key if config.has_api_key() else None,
        db_confidence_threshold=0.90,
        enable_learning=False,  # Disable for testing
        test_mode=True
    )
    
    # Test cases
    test_transactions = [
        {
            'description': 'WOOLWORTHS ASHWOOD',
            'amount': -45.50,
            'bs_category': 'Groceries'
        },
        {
            'description': 'DAN MURPHY\'S MALVERN',
            'amount': -72.00,
            'bs_category': 'Alcohol'
        },
        {
            'description': 'PENDING - POS AUTHORISATION CHEMIST WAREHOUSE CHADSTONE',
            'amount': -15.99,
            'bs_category': 'Health'
        },
        {
            'description': 'ANZ M-BANKING FUNDS TFER TRANSFER 190891 TO 013017655923834',
            'amount': -100.00,
            'bs_category': 'Internal Transfer',
            'account_number': '655923834'
        },
        {
            'description': 'NETFLIX.COM',
            'amount': -16.99,
            'bs_category': 'Online Retail and Subscription Services'
        },
    ]
    
    print("\nTesting Final Transaction Categorizer")
    print("=" * 80)
    
    for tx in test_transactions:
        category, confidence, source = categorizer.categorize(tx)
        print(f"\nDescription: {tx['description']}")
        print(f"BS Category: {tx.get('bs_category', 'N/A')}")
        print(f"Result: {category} (confidence: {confidence:.2f}, source: {source})")
    
    categorizer.print_statistics()

