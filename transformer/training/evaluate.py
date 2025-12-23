#!/usr/bin/env python3
"""
Evaluation Script for BERT Transaction Categorizer

Provides detailed evaluation metrics:
- Overall accuracy
- Per-category precision/recall/F1
- Confusion matrix
- Confidence distribution
- Error analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from tqdm import tqdm

from data_loader import create_dataloaders
from bert_classifier import create_model


def convert_to_python_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_python_types(item) for item in obj]
    else:
        return obj


def evaluate_model(
    model: nn.Module,
    test_loader,
    device: torch.device,
    idx_to_label: dict
) -> dict:
    """
    Comprehensive model evaluation.
    
    Returns dictionary with:
    - accuracy
    - per_category_metrics
    - confusion_matrix
    - predictions (with confidences)
    - errors (misclassified samples)
    """
    model.eval()
    
    all_predictions = []
    all_labels = []
    all_confidences = []
    all_transaction_ids = []
    
    print("Running evaluation...")
    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)
            
            # Get predictions and confidences
            predictions, confidences = model.predict(input_ids, attention_mask)
            
            all_predictions.extend(predictions.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_confidences.extend(confidences.cpu().numpy())
            all_transaction_ids.extend(batch['transaction_id'])
    
    # Convert to numpy arrays
    predictions = np.array(all_predictions)
    labels = np.array(all_labels)
    confidences = np.array(all_confidences)
    
    # Overall accuracy
    accuracy = (predictions == labels).mean() * 100
    
    # Get unique labels present in test set
    unique_labels = sorted(set(labels.tolist()))
    label_names = [idx_to_label[i] for i in unique_labels]
    
    # Per-category metrics (only for labels in test set)
    report = classification_report(
        labels,
        predictions,
        labels=unique_labels,  # Specify only labels in test set
        target_names=label_names,
        output_dict=True,
        zero_division=0
    )
    
    # Confusion matrix
    conf_matrix = confusion_matrix(labels, predictions)
    
    # Error analysis
    errors = []
    for i, (pred, true_label, conf, tx_id) in enumerate(
        zip(predictions, labels, confidences, all_transaction_ids)
    ):
        if pred != true_label:
            errors.append({
                'transaction_id': tx_id,
                'predicted': idx_to_label[pred],
                'true': idx_to_label[true_label],
                'confidence': float(conf)
            })
    
    # Confidence distribution
    conf_bins = {
        'very_low': (confidences < 0.5).sum(),
        'low': ((confidences >= 0.5) & (confidences < 0.7)).sum(),
        'medium': ((confidences >= 0.7) & (confidences < 0.9)).sum(),
        'high': (confidences >= 0.9).sum(),
    }
    
    results = {
        'accuracy': accuracy,
        'num_samples': len(labels),
        'num_correct': (predictions == labels).sum(),
        'num_errors': len(errors),
        'classification_report': report,
        'confusion_matrix': conf_matrix.tolist(),
        'confidence_distribution': {k: int(v) for k, v in conf_bins.items()},
        'mean_confidence': float(confidences.mean()),
        'errors': errors[:50]  # Store first 50 errors
    }
    
    return results


def print_evaluation_summary(results: dict, idx_to_label: dict):
    """Print human-readable evaluation summary."""
    print(f"\n{'='*70}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*70}\n")
    
    print(f"Overall Accuracy: {results['accuracy']:.2f}%")
    print(f"  Correct: {results['num_correct']} / {results['num_samples']}")
    print(f"  Errors: {results['num_errors']}")
    
    print(f"\nConfidence Distribution:")
    conf_dist = results['confidence_distribution']
    total = sum(conf_dist.values())
    for level, count in conf_dist.items():
        pct = 100 * count / total if total > 0 else 0
        print(f"  {level:10s}: {count:4d} ({pct:5.1f}%)")
    print(f"  Mean confidence: {results['mean_confidence']:.3f}")
    
    # Top performing categories
    report = results['classification_report']
    categories = [(k, v) for k, v in report.items() if k in idx_to_label.values()]
    categories_sorted = sorted(categories, key=lambda x: x[1]['f1-score'], reverse=True)
    
    print(f"\nTop 10 Best Performing Categories (by F1-score):")
    print(f"  {'Category':<12} {'Precision':>9} {'Recall':>9} {'F1-Score':>9} {'Support':>9}")
    print(f"  {'-'*60}")
    for cat, metrics in categories_sorted[:10]:
        print(f"  {cat:<12} {metrics['precision']:>9.3f} {metrics['recall']:>9.3f} "
              f"{metrics['f1-score']:>9.3f} {metrics['support']:>9.0f}")
    
    print(f"\nTop 10 Worst Performing Categories (by F1-score):")
    print(f"  {'Category':<12} {'Precision':>9} {'Recall':>9} {'F1-Score':>9} {'Support':>9}")
    print(f"  {'-'*60}")
    for cat, metrics in categories_sorted[-10:]:
        if metrics['support'] > 0:  # Only show categories with test samples
            print(f"  {cat:<12} {metrics['precision']:>9.3f} {metrics['recall']:>9.3f} "
                  f"{metrics['f1-score']:>9.3f} {metrics['support']:>9.0f}")
    
    # Most common errors
    if results['errors']:
        print(f"\nMost Common Misclassifications:")
        error_pairs = defaultdict(int)
        for error in results['errors']:
            pair = (error['true'], error['predicted'])
            error_pairs[pair] += 1
        
        sorted_errors = sorted(error_pairs.items(), key=lambda x: x[1], reverse=True)
        print(f"  {'True':<12} {'→ Predicted':<12} {'Count':>6}")
        print(f"  {'-'*35}")
        for (true, pred), count in sorted_errors[:10]:
            print(f"  {true:<12} → {pred:<12} {count:>6}")
    
    print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Evaluate BERT transaction categorizer')
    parser.add_argument(
        '--data',
        type=Path,
        default=Path('data/datasets/features_prod.csv'),
        help='Path to features CSV'
    )
    parser.add_argument(
        '--model-dir',
        type=Path,
        default=Path('models/bert_transaction_categorizer'),
        help='Directory containing trained model'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Batch size for evaluation'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Output path for evaluation results JSON'
    )
    
    args = parser.parse_args()
    
    # Load label mappings
    with (args.model_dir / 'label_mappings.json').open() as f:
        mappings = json.load(f)
    
    label_to_idx = {k: int(v) for k, v in mappings['label_to_idx'].items()}
    idx_to_label = {int(k): v for k, v in mappings['idx_to_label'].items()}
    model_name = mappings['model_name']
    num_labels = len(label_to_idx)
    
    print(f"Model: {model_name}")
    print(f"Categories: {num_labels}")
    
    # Setup device
    if torch.backends.mps.is_available():
        device = torch.device('mps')
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')
    print(f"Device: {device}")
    
    # Load data
    print(f"\nLoading test data...")
    _, test_loader, _, _, _ = create_dataloaders(
        args.data,
        model_name=model_name,
        batch_size=args.batch_size
    )
    
    # Load model
    print(f"\nLoading model from {args.model_dir / 'best_model.pt'}...")
    checkpoint = torch.load(args.model_dir / 'best_model.pt', map_location=device)
    
    # Create model with class weights (to match training)
    model = create_model(
        num_labels=num_labels,
        model_name=model_name,
        use_class_weights=True,  # Match training setup
        class_weights=torch.zeros(num_labels)  # Dummy weights, will be loaded from checkpoint
    )
    
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    
    print(f"Model loaded from epoch {checkpoint['epoch'] + 1}")
    print(f"  Checkpoint test accuracy: {checkpoint['test_acc']:.2f}%")
    
    # Evaluate
    results = evaluate_model(model, test_loader, device, idx_to_label)
    
    # Print summary
    print_evaluation_summary(results, idx_to_label)
    
    # Save results
    if args.output:
        output_path = args.output
    else:
        output_path = args.model_dir / 'evaluation_results.json'
    
    # Remove confusion matrix and convert types
    results_to_save = {k: v for k, v in results.items() if k != 'confusion_matrix'}
    results_to_save = convert_to_python_types(results_to_save)
    
    with output_path.open('w') as f:
        json.dump(results_to_save, f, indent=2)
    
    print(f"✓ Evaluation results saved to: {output_path}")


if __name__ == '__main__':
    main()

