#!/usr/bin/env python3
"""
Test script for hybrid learning system

Tests normalization, learning, and categorization without making real API calls.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from transformer.inference.normalizer import normalize_description, test_normalization
from transformer.inference.learned_patterns import LearnedPatternsManager
from transformer.inference.claude_categorizer import ClaudeCategorizer
from transformer.config.api_config import get_config


def test_normalizer():
    """Test the normalization function."""
    print("\n" + "="*80)
    print("TEST 1: NORMALIZATION")
    print("="*80)
    
    test_normalization()
    
    print("\n✅ Normalization test complete")


def test_learned_patterns():
    """Test the learned patterns manager."""
    print("\n" + "="*80)
    print("TEST 2: LEARNED PATTERNS MANAGER")
    print("="*80)
    
    # Create test manager
    test_path = Path('data/test_learned_patterns.json')
    manager = LearnedPatternsManager(test_path)
    
    # Add some test patterns
    patterns_to_learn = [
        ("WOOLWORTHS 1234 MELBOURNE", "EXP-016", 0.97),
        ("KFC PARRAMATTA NSW", "EXP-008", 0.96),
        ("PAYMENT TO MOMENTUM ENERGY 23522784", "EXP-040", 0.95),
    ]
    
    print("\nAdding test patterns...")
    for desc, category, conf in patterns_to_learn:
        added = manager.add_pattern(desc, category, conf)
        normalized = normalize_description(desc)
        print(f"  {normalized:30s} → {category} (added: {added})")
    
    # Test lookup
    print("\nTesting lookups...")
    test_lookups = [
        "WOOLWORTHS 5678 SYDNEY",  # Should match woolworths
        "KFC MELBOURNE VIC",  # Should match kfc
        "COLES 1234",  # Should not match (not learned)
    ]
    
    for desc in test_lookups:
        result = manager.lookup(desc)
        if result:
            print(f"  ✓ '{desc}' → {result.category} (conf: {result.confidence})")
        else:
            print(f"  ✗ '{desc}' → Not found")
    
    # Get statistics
    print("\nStatistics:")
    stats = manager.get_statistics()
    for key, value in stats.items():
        if key not in ['category_distribution', 'source_distribution', 'top_patterns']:
            print(f"  {key}: {value}")
    
    # Cleanup
    if test_path.exists():
        test_path.unlink()
    
    print("\n✅ Learned patterns test complete")


def test_claude_categorizer():
    """Test Claude categorizer in test mode."""
    print("\n" + "="*80)
    print("TEST 3: CLAUDE CATEGORIZER (TEST MODE)")
    print("="*80)
    
    # Create categorizer in test mode (no real API calls)
    categorizer = ClaudeCategorizer(test_mode=True)
    
    test_transactions = [
        ("KFC PARRAMATTA NSW", -15.50, "Dining Out"),
        ("WOOLWORTHS 1234 SYDNEY", -85.30, "Groceries"),
        ("PAYMENT TO MOMENTUM ENERGY", -167.23, "Utilities"),
        ("PAY/SALARY FROM VIC BUILDING", 3606.77, "Wages"),
    ]
    
    print("\nTest predictions (simulated, no API charges):")
    for desc, amount, bs_cat in test_transactions:
        category, confidence, reasoning = categorizer.predict(desc, amount, bs_cat)
        print(f"  {desc:40s} → {category} (conf: {confidence:.2f})")
        print(f"    Reasoning: {reasoning}")
    
    # Get statistics
    stats = categorizer.get_statistics()
    print("\nStatistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Claude categorizer test complete")


def test_config():
    """Test configuration management."""
    print("\n" + "="*80)
    print("TEST 4: CONFIGURATION")
    print("="*80)
    
    config = get_config()
    
    print("\nCurrent configuration:")
    for key, value in config.get_summary().items():
        print(f"  {key}: {value}")
    
    is_valid, error = config.validate()
    if is_valid:
        print("\n✅ Configuration is valid")
    else:
        print(f"\n⚠️  Configuration issue: {error}")
        print("\nThis is expected if you haven't set up your API key yet.")
        print("To set up, run:")
        print("  export ANTHROPIC_API_KEY=your-key-here")
        print("Or create a .env file with your key.")
    
    print("\n✅ Configuration test complete")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("HYBRID LEARNING SYSTEM - TEST SUITE")
    print("="*80)
    
    try:
        test_normalizer()
        test_learned_patterns()
        test_claude_categorizer()
        test_config()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETE ✅")
        print("="*80)
        print("\nNext steps:")
        print("1. Set up your Anthropic API key (see TEST 4 output)")
        print("2. Run: python3 transformer/inference/categorize_statements.py")
        print("3. Check learning statistics after processing transactions")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

