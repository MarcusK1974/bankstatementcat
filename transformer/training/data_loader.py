#!/usr/bin/env python3
"""
Data Loader for BERT Transaction Categorizer

Loads production-ready features from features_prod.csv and prepares
PyTorch DataLoaders for training and evaluation.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer


@dataclass
class TransactionSample:
    """Single transaction sample"""
    description: str
    amount: float
    month: int
    day_of_week: int
    day_of_month: int
    amount_bucket: str
    label: str
    transaction_id: str
    split: str


class TransactionDataset(Dataset):
    """PyTorch Dataset for transaction categorization"""
    
    def __init__(
        self,
        samples: List[TransactionSample],
        tokenizer: BertTokenizer,
        label_to_idx: Dict[str, int],
        max_length: int = 128
    ):
        self.samples = samples
        self.tokenizer = tokenizer
        self.label_to_idx = label_to_idx
        self.max_length = max_length
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        sample = self.samples[idx]
        
        # Tokenize description
        encoding = self.tokenizer(
            sample.description,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        # Get label index
        label_idx = self.label_to_idx[sample.label]
        
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': torch.tensor(label_idx, dtype=torch.long),
            'transaction_id': sample.transaction_id,
        }


def load_dataset(csv_path: Path) -> Tuple[List[TransactionSample], Dict[str, int]]:
    """
    Load transaction dataset from CSV.
    
    Returns:
        samples: List of transaction samples
        label_to_idx: Mapping from BASIQ code to integer index
    """
    samples = []
    labels = set()
    
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip if no label
            label = row.get('label_group_code', '').strip()
            if not label:
                continue
            
            labels.add(label)
            
            # Parse fields
            try:
                amount = float(row.get('amount', '0'))
                month = int(row.get('month', '0'))
                day_of_week = int(row.get('day_of_week', '0'))
                day_of_month = int(row.get('day_of_month', '0'))
            except ValueError:
                amount = 0.0
                month = 0
                day_of_week = 0
                day_of_month = 0
            
            sample = TransactionSample(
                description=row.get('description', ''),
                amount=amount,
                month=month,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                amount_bucket=row.get('amount_bucket', 'medium'),
                label=label,
                transaction_id=row.get('transaction_id', ''),
                split=row.get('split', 'train')
            )
            samples.append(sample)
    
    # Create label to index mapping (sorted for consistency)
    label_to_idx = {label: idx for idx, label in enumerate(sorted(labels))}
    
    print(f"Loaded {len(samples)} samples")
    print(f"Found {len(labels)} unique labels")
    
    return samples, label_to_idx


def create_dataloaders(
    csv_path: Path,
    model_name: str = 'bert-base-uncased',
    batch_size: int = 16,
    max_length: int = 128,
) -> Tuple[DataLoader, DataLoader, Dict[str, int], Dict[int, str], BertTokenizer]:
    """
    Create train and test DataLoaders.
    
    Args:
        csv_path: Path to features_prod.csv
        model_name: HuggingFace model name for tokenizer
        batch_size: Batch size for training
        max_length: Max sequence length for BERT
    
    Returns:
        train_loader: Training DataLoader
        test_loader: Test DataLoader
        label_to_idx: Label to index mapping
        idx_to_label: Index to label mapping
        tokenizer: BERT tokenizer
    """
    # Load tokenizer
    print(f"Loading tokenizer: {model_name}")
    tokenizer = BertTokenizer.from_pretrained(model_name)
    
    # Load dataset
    print(f"Loading dataset from: {csv_path}")
    samples, label_to_idx = load_dataset(csv_path)
    idx_to_label = {idx: label for label, idx in label_to_idx.items()}
    
    # Split by split column
    train_samples = [s for s in samples if s.split == 'train']
    test_samples = [s for s in samples if s.split == 'test']
    
    print(f"\nTrain samples: {len(train_samples)}")
    print(f"Test samples: {len(test_samples)}")
    
    # Count label distribution
    train_label_counts = Counter(s.label for s in train_samples)
    test_label_counts = Counter(s.label for s in test_samples)
    
    print(f"\nTop 10 training labels:")
    for label, count in train_label_counts.most_common(10):
        print(f"  {label}: {count}")
    
    print(f"\nTop 10 test labels:")
    for label, count in test_label_counts.most_common(10):
        print(f"  {label}: {count}")
    
    # Create datasets
    train_dataset = TransactionDataset(train_samples, tokenizer, label_to_idx, max_length)
    test_dataset = TransactionDataset(test_samples, tokenizer, label_to_idx, max_length)
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,  # Use 0 for MPS compatibility
        pin_memory=False  # Disable for MPS
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False
    )
    
    # Calculate class weights for handling imbalance
    class_weights = compute_class_weights(train_label_counts, label_to_idx)
    print(f"\nClass weight range: {class_weights.min():.3f} to {class_weights.max():.3f}")
    
    return train_loader, test_loader, label_to_idx, idx_to_label, tokenizer


def compute_class_weights(label_counts: Counter, label_to_idx: Dict[str, int]) -> torch.Tensor:
    """
    Compute class weights for handling imbalanced dataset.
    Uses inverse frequency weighting.
    """
    num_classes = len(label_to_idx)
    weights = torch.zeros(num_classes)
    
    total_samples = sum(label_counts.values())
    
    for label, idx in label_to_idx.items():
        count = label_counts.get(label, 1)  # Avoid division by zero
        # Inverse frequency weight
        weights[idx] = total_samples / (num_classes * count)
    
    return weights


if __name__ == '__main__':
    # Test data loader
    csv_path = Path('data/datasets/features_prod.csv')
    
    train_loader, test_loader, label_to_idx, idx_to_label, tokenizer = create_dataloaders(
        csv_path,
        batch_size=16
    )
    
    print(f"\n✓ Data loaders created successfully")
    print(f"  Training batches: {len(train_loader)}")
    print(f"  Test batches: {len(test_loader)}")
    
    # Test a batch
    print(f"\nTesting batch...")
    batch = next(iter(train_loader))
    print(f"  input_ids shape: {batch['input_ids'].shape}")
    print(f"  attention_mask shape: {batch['attention_mask'].shape}")
    print(f"  labels shape: {batch['labels'].shape}")
    print(f"  Sample label: {idx_to_label[batch['labels'][0].item()]}")

