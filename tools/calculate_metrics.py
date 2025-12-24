#!/usr/bin/env python3
"""
CLI tool for calculating enrichment metrics from categorized bank statements.

Usage:
    # Single customer
    python tools/calculate_metrics.py --input data/output/persona1_categorized.csv --output results/persona1_metrics.json
    
    # Batch processing
    python tools/calculate_metrics.py --batch data/output/ --output-csv results/all_metrics.csv --output-json results/all_metrics.json
    
    # Export schema
    python tools/calculate_metrics.py --export-schema results/metrics_schema.json
"""
import argparse
import sys
from pathlib import Path
import glob

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transformer.metrics import MetricsEngine


def main():
    parser = argparse.ArgumentParser(
        description='Calculate enrichment metrics from categorized bank statements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--input', '-i', 
                       help='Input CSV file with categorized transactions')
    parser.add_argument('--batch', '-b',
                       help='Directory containing multiple categorized CSV files')
    parser.add_argument('--output', '-o',
                       help='Output file path (JSON for single, CSV for batch)')
    parser.add_argument('--output-csv',
                       help='Output CSV path for batch processing')
    parser.add_argument('--output-json',
                       help='Output JSON path for batch processing')
    parser.add_argument('--customer-id',
                       help='Customer ID (defaults to filename)')
    parser.add_argument('--export-schema',
                       help='Export metrics schema to JSON file')
    parser.add_argument('--config',
                       default='transformer/config/metrics_config.yaml',
                       help='Path to metrics configuration file')
    
    args = parser.parse_args()
    
    # Initialize engine
    engine = MetricsEngine(args.config)
    
    # Export schema
    if args.export_schema:
        engine.export_metrics_schema(args.export_schema)
        print(f"\n✓ Schema exported successfully")
        return 0
    
    # Single file processing
    if args.input:
        print(f"\nProcessing: {args.input}")
        print("=" * 80)
        
        metrics = engine.process_single_file(args.input, args.customer_id)
        
        if args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"\n✓ Metrics exported to: {args.output}")
        else:
            import json
            print("\nMetrics:")
            print(json.dumps(metrics, indent=2))
        
        return 0
    
    # Batch processing
    if args.batch:
        batch_dir = Path(args.batch)
        
        # Find all CSV files
        csv_files = sorted(glob.glob(str(batch_dir / '*categorized*.csv')))
        
        if not csv_files:
            print(f"ERROR: No *categorized*.csv files found in {batch_dir}")
            return 1
        
        print(f"\nBatch Processing: {len(csv_files)} files")
        print("=" * 80)
        
        results_df = engine.process_batch(
            csv_files,
            output_csv=args.output_csv or args.output,
            output_json=args.output_json
        )
        
        print(f"\n✓ Processed {len(results_df)} customers successfully")
        
        # Print summary stats
        print("\nSummary Statistics:")
        print("=" * 80)
        print(f"Average Income (ME033): ${results_df['ME033'].mean():.2f}")
        print(f"Average Outgoings (ME034): ${results_df['ME034'].mean():.2f}")
        print(f"Customers with SACC loans: {(results_df['ME017'] > 0).sum()}")
        print(f"Customers with dishonours: {(results_df['ME019'] > 0).sum()}")
        print(f"Customers with unemployment benefits: {results_df['ME031'].sum()}")
        
        return 0
    
    # No action specified
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())

