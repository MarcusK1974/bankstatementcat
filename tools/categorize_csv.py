#!/usr/bin/env python3
"""
Categorize a CSV file using the smart direction-aware categorizer
"""

import pandas as pd
import sys
import os
from pathlib import Path
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from transformer.inference.predictor_final import FinalTransactionCategorizer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def load_basiq_descriptions():
    """Load BASIQ category descriptions"""
    basiq_path = project_root / 'docs' / 'basiq_groups.yaml'
    with open(basiq_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Handle structure with 'groups' key
    groups = data['groups'] if 'groups' in data else data
    return {g['code']: g['name'] for g in groups}

def categorize_file(input_path: str, output_path: str, enable_claude: bool = False):
    """Categorize transactions in a CSV file"""
    
    # Load input
    df = pd.read_csv(input_path)
    print(f"\nLoaded {len(df)} transactions from {input_path}")
    
    # Initialize categorizer
    api_key = os.getenv('ANTHROPIC_API_KEY') if enable_claude else None
    categorizer = FinalTransactionCategorizer(
        api_key=api_key,
        db_confidence_threshold=0.90,
        enable_learning=enable_claude,
        test_mode=not enable_claude
    )
    
    # Load descriptions
    descriptions = load_basiq_descriptions()
    
    # Categorize each transaction
    results = []
    for idx, row in df.iterrows():
        transaction = {
            'description': row.get('description', ''),
            'amount': row.get('amount', 0),
            'bs_category': row.get('bs_category'),
            'account_number': row.get('account_number'),
            'third_party': row.get('third_party'),
        }
        
        category, confidence, source = categorizer.categorize(transaction)
        
        results.append({
            'category': category,
            'confidence': confidence,
            'source': source,
            'description_long': descriptions.get(category, 'Unknown')
        })
    
    # Add results to dataframe
    df['basiq_category'] = [r['category'] for r in results]
    df['basiq_category_code'] = [r['category'] for r in results]
    df['basiq_category_description'] = [r['description_long'] for r in results]
    df['confidence'] = [r['confidence'] for r in results]
    df['source'] = [r['source'] for r in results]
    
    # Save
    df.to_csv(output_path, index=False)
    print(f"Saved categorized transactions to {output_path}")
    
    # Print statistics
    print("\n" + "=" * 80)
    print("CATEGORIZATION STATISTICS")
    print("=" * 80)
    stats = categorizer.stats
    for key, value in stats.items():
        if value > 0:
            pct = (value / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"  {key:30s}: {value:4d} ({pct:5.1f}%)")
    print()
    
    return df

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python categorize_csv.py <input.csv> <output.csv> [--claude]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    enable_claude = '--claude' in sys.argv
    
    categorize_file(input_file, output_file, enable_claude)

