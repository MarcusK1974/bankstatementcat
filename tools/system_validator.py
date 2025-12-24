#!/usr/bin/env python3
"""
System Validator - Proactive Bug Detection

Runs comprehensive checks to catch issues BEFORE they hit production:
- Data completeness (taxonomy, mappings)
- Code consistency (method signatures, return types)
- Configuration validity (API keys, paths)
- Integration correctness (cross-module compatibility)
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Tuple
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from transformer.config.australian_brands_comprehensive import BRAND_RULES
from transformer.inference.predictor_final import FinalTransactionCategorizer


class SystemValidator:
    """Comprehensive system validation."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.project_root = Path(__file__).parent.parent
        
    def run_all_checks(self) -> bool:
        """Run all validation checks. Returns True if all pass."""
        print("=" * 80)
        print("SYSTEM VALIDATOR - Proactive Bug Detection")
        print("=" * 80)
        print()
        
        self.check_basiq_taxonomy()
        self.check_comprehensive_database()
        self.check_bs_mappings()
        self.check_code_consistency()
        self.check_api_configuration()
        self.check_normalizer_functionality()  # NEW: Catch normalizer bugs
        self.check_data_flow_integrity()
        
        # Print results
        print()
        print("=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        print()
        
        if self.errors:
            print(f"❌ ERRORS FOUND: {len(self.errors)}")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
            print()
        
        if self.warnings:
            print(f"⚠️  WARNINGS: {len(self.warnings)}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
            print()
        
        if not self.errors and not self.warnings:
            print("✅ ALL CHECKS PASSED - System is healthy")
            print()
        
        return len(self.errors) == 0
    
    def check_basiq_taxonomy(self):
        """Check BASIQ groups taxonomy completeness."""
        print("1. Checking BASIQ Taxonomy...")
        
        basiq_path = self.project_root / 'docs' / 'basiq_groups.yaml'
        if not basiq_path.exists():
            self.errors.append(f"BASIQ taxonomy not found at {basiq_path}")
            return
        
        with open(basiq_path, 'r') as f:
            data = yaml.safe_load(f)
        
        groups = {g['code']: g for g in data.get('groups', [])}
        
        # Check for categories used in comprehensive DB but missing in taxonomy
        used_categories = set(rule[1] for rule in BRAND_RULES)
        missing_categories = used_categories - set(groups.keys())
        
        if missing_categories:
            for cat in missing_categories:
                self.errors.append(
                    f"Category {cat} used in comprehensive DB but MISSING in basiq_groups.yaml"
                )
        
        # Check for standard categories
        expected_categories = [
            'EXP-034',  # Superannuation
            'EXP-035',  # Subscription Media & Software
            'EXP-039',  # Uncategorised Debits
            'EXP-061',  # Credit Card Repayments
            'INC-007',  # Other Credits
        ]
        
        for cat in expected_categories:
            if cat not in groups:
                self.errors.append(f"Standard category {cat} MISSING from taxonomy")
        
        print(f"   ✓ Found {len(groups)} categories in taxonomy")
        print()
    
    def check_comprehensive_database(self):
        """Check comprehensive brand database for completeness and patterns."""
        print("2. Checking Comprehensive Database...")
        
        # Check for common gaps
        all_keywords = []
        for keywords, cat, conf, reason in BRAND_RULES:
            all_keywords.extend(keywords)
        
        all_keywords_lower = [k.lower() for k in all_keywords]
        
        # Check for self-awareness
        if 'cursor' not in all_keywords_lower and 'cursor.com' not in all_keywords_lower:
            self.warnings.append(
                "Cursor AI not in database (ironic!) - should add to EXP-035"
            )
        
        # CRITICAL: Check for fashion brands miscategorized as Dishonours (EXP-009)
        fashion_keywords = ['zara', 'h&m', 'uniqlo', 'cotton on', 'nike', 'adidas']
        for keyword in fashion_keywords:
            from transformer.config.australian_brands_comprehensive import get_category
            result = get_category(keyword)
            if result[0] == 'EXP-009':
                self.errors.append(
                    f"CRITICAL: '{keyword}' miscategorized as EXP-009 (Dishonours) instead of EXP-031 (Retail)"
                )
        
        # CRITICAL: Check dishonour/bad behavior fees are in EXP-009
        bad_behavior_keywords = ['honour fee', 'dishonour fee', 'overdrawn fee', 'overdraft fee']
        for keyword in bad_behavior_keywords:
            from transformer.config.australian_brands_comprehensive import get_category
            result = get_category(keyword)
            if not result[0]:
                self.errors.append(
                    f"CRITICAL: '{keyword}' not in database - must be EXP-009 for credit assessment"
                )
            elif result[0] != 'EXP-009':
                self.errors.append(
                    f"CRITICAL: '{keyword}' is {result[0]} but should be EXP-009 (Dishonours) for credit assessment"
                )
        
        # Check for generic patterns vs. exhaustive lists
        categories_needing_generic_patterns = {
            'EXP-034': 'superannuation',  # 100+ super funds in Australia
        }
        
        for cat, domain in categories_needing_generic_patterns.items():
            cat_rules = [r for r in BRAND_RULES if r[1] == cat]
            has_generic = any(
                any(len(kw.split()) == 1 and domain in kw for kw in keywords)
                for keywords, _, _, _ in cat_rules
            )
            
            if not has_generic:
                self.warnings.append(
                    f"Category {cat} ({domain}) uses exhaustive list without generic fallback pattern"
                )
        
        print(f"   ✓ Database has {len(BRAND_RULES)} rules")
        print()
    
    def check_bs_mappings(self):
        """Check BS category mappings for completeness."""
        print("3. Checking BS Category Mappings...")
        
        bs_path = self.project_root / 'data' / 'datasets' / 'bs_category_mappings.json'
        if not bs_path.exists():
            self.warnings.append(f"BS mappings not found at {bs_path}")
            return
        
        with open(bs_path, 'r') as f:
            data = json.load(f)
        
        mappings = data.get('mappings', {})
        
        # Check for generic/unclear categories
        generic_categories = ['Third Party Payment Providers', 'Uncategorised']
        for cat in generic_categories:
            if cat in mappings:
                mapped = mappings[cat]
                if mapped.get('basiq_group') in ['EXP-039', 'INC-007']:
                    self.warnings.append(
                        f"BS category '{cat}' maps to uncategorized - "
                        f"these should trigger Claude for learning"
                    )
        
        print(f"   ✓ Found {len(mappings)} BS category mappings")
        print()
    
    def check_code_consistency(self):
        """Check code consistency across modules."""
        print("4. Checking Code Consistency...")
        
        try:
            # Try to initialize categorizer
            categorizer = FinalTransactionCategorizer(api_key=None)
            
            # Check if methods exist
            required_methods = ['categorize', 'get_stats', 'get_statistics']
            for method in required_methods:
                if not hasattr(categorizer, method):
                    self.errors.append(
                        f"FinalTransactionCategorizer missing required method: {method}"
                    )
            
            print("   ✓ FinalTransactionCategorizer initialized successfully")
        except Exception as e:
            self.errors.append(f"Failed to initialize FinalTransactionCategorizer: {e}")
        
        print()
    
    def check_api_configuration(self):
        """Check API configuration."""
        print("5. Checking API Configuration...")
        
        try:
            from transformer.config import api_config
            config = api_config.Config()
            
            if config.anthropic_api_key:
                print("   ✓ Claude API key configured")
            else:
                self.warnings.append(
                    "Claude API key not configured - learning functionality disabled"
                )
        except Exception as e:
            self.warnings.append(f"Failed to load API config: {e}")
        
        print()
    
    def check_normalizer_functionality(self):
        """Check that transaction normalizer is working correctly."""
        print("6. Checking Transaction Normalizer...")
        
        try:
            from transformer.inference.transaction_normalizer import normalize_description
            from transformer.config.australian_brands_comprehensive import get_category
            
            # Test cases: [description, should_be_stripped_to, should_find_in_db]
            test_cases = [
                (
                    "ANZ INTERNET BANKING BPAY AWARE SUPER PERS D {529890}",
                    "aware super",
                    True,  # Should find in DB
                    "EXP-034"
                ),
                (
                    "VISA DEBIT PURCHASE CARD 3960 WOOLWORTHS TEST",
                    "woolworths",
                    True,
                    "EXP-016"
                ),
                (
                    "PENDING - POS AUTHORISATION BELAIR FINE WINES BELAIR AU",
                    "belair fine wines",
                    True,
                    None  # Don't check specific category
                ),
            ]
            
            normalizer_working = True
            
            for original, expected_merchant_part, should_find, expected_cat in test_cases:
                merchant, tx_type = normalize_description(original)
                merchant_lower = merchant.lower()
                
                # Check if prefix was stripped correctly
                if "anz internet banking" in merchant_lower or "visa debit purchase card" in merchant_lower:
                    self.errors.append(
                        f"Normalizer FAILED to strip prefix from: '{original[:50]}...' "
                        f"→ Result: '{merchant}'"
                    )
                    normalizer_working = False
                    continue
                
                # Check if merchant name is present
                if expected_merchant_part not in merchant_lower:
                    self.errors.append(
                        f"Normalizer output '{merchant}' doesn't contain expected '{expected_merchant_part}'"
                    )
                    normalizer_working = False
                    continue
                
                # Check DB lookup
                if should_find:
                    db_result = get_category(merchant_lower)
                    if not db_result[0]:
                        self.warnings.append(
                            f"Normalized '{merchant}' not found in comprehensive DB (expected to be there)"
                        )
                    elif expected_cat and db_result[0] != expected_cat:
                        self.warnings.append(
                            f"'{merchant}' → {db_result[0]} (expected {expected_cat})"
                        )
            
            if normalizer_working:
                print("   ✓ Transaction normalizer stripping prefixes correctly")
            else:
                print("   ✗ Transaction normalizer has issues")
                
        except Exception as e:
            self.errors.append(f"Normalizer check failed: {e}")
        
        print()
    
    def check_data_flow_integrity(self):
        """Check data flow integrity - simulate a transaction."""
        print("7. Checking Data Flow Integrity...")
        
        try:
            categorizer = FinalTransactionCategorizer(api_key=None)
            
            # Test transaction
            test_tx = {
                'description': 'WOOLWORTHS TEST',
                'amount': -50,
                'bs_category': 'Groceries',
                'category': 'Groceries',
                'third_party': '',
            }
            
            category, confidence, source = categorizer.categorize(test_tx)
            
            if category == 'Unknown':
                self.errors.append(
                    "Categorizer returned 'Unknown' - check BASIQ groups lookup"
                )
            
            # Check if category exists in taxonomy
            basiq_path = self.project_root / 'docs' / 'basiq_groups.yaml'
            with open(basiq_path, 'r') as f:
                data = yaml.safe_load(f)
            groups = {g['code']: g for g in data.get('groups', [])}
            
            if category not in groups and category != 'INTERNAL_TRANSFER':
                self.errors.append(
                    f"Categorizer returned {category} which doesn't exist in taxonomy"
                )
            
            print(f"   ✓ Test transaction: {category} (confidence: {confidence:.2f})")
        except Exception as e:
            self.errors.append(f"Data flow test failed: {e}")
        
        print()


def main():
    """Run system validation."""
    validator = SystemValidator()
    success = validator.run_all_checks()
    
    if not success:
        print("=" * 80)
        print("⚠️  VALIDATION FAILED - Fix errors before running production")
        print("=" * 80)
        sys.exit(1)
    else:
        print("=" * 80)
        print("✅ SYSTEM READY FOR PRODUCTION")
        print("=" * 80)
        sys.exit(0)


if __name__ == '__main__':
    main()

