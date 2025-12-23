#!/usr/bin/env python3
"""
Training Script for BERT Transaction Categorizer

Trains BERT model with:
- MPS acceleration (Apple Silicon GPU)
- Weighted loss for class imbalance
- Early stopping
- Model checkpointing
- TensorBoard logging
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.tensorboard import SummaryWriter
from transformers import get_linear_schedule_with_warmup
from tqdm import tqdm

from data_loader import create_dataloaders, compute_class_weights
from bert_classifier import create_model


def train_epoch(
    model: nn.Module,
    train_loader,
    optimizer,
    scheduler,
    device: torch.device,
    epoch: int,
    writer: SummaryWriter = None
) -> float:
    """Train for one epoch."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1} [Train]")
    
    for batch_idx, batch in enumerate(progress_bar):
        # Move batch to device
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)
        
        # Zero gradients
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(input_ids, attention_mask, labels)
        loss = outputs['loss']
        
        # Backward pass
        loss.backward()
        
        # Gradient clipping (prevent exploding gradients)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        # Update weights
        optimizer.step()
        scheduler.step()
        
        # Track metrics
        total_loss += loss.item()
        predictions = outputs['logits'].argmax(dim=-1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)
        
        # Update progress bar
        avg_loss = total_loss / (batch_idx + 1)
        accuracy = 100.0 * correct / total
        progress_bar.set_postfix({
            'loss': f'{avg_loss:.4f}',
            'acc': f'{accuracy:.2f}%'
        })
        
        # TensorBoard logging
        if writer is not None:
            global_step = epoch * len(train_loader) + batch_idx
            writer.add_scalar('Train/Loss', loss.item(), global_step)
            writer.add_scalar('Train/Accuracy', accuracy, global_step)
            writer.add_scalar('Train/LearningRate', scheduler.get_last_lr()[0], global_step)
    
    epoch_loss = total_loss / len(train_loader)
    epoch_acc = 100.0 * correct / total
    
    return epoch_loss, epoch_acc


def evaluate(
    model: nn.Module,
    test_loader,
    device: torch.device,
    epoch: int = None,
    writer: SummaryWriter = None
) -> tuple[float, float]:
    """Evaluate model on test set."""
    model.eval()
    total_loss = 0
    correct = 0
    total = 0
    
    all_predictions = []
    all_labels = []
    all_confidences = []
    
    desc = f"Epoch {epoch+1} [Eval]" if epoch is not None else "Evaluation"
    progress_bar = tqdm(test_loader, desc=desc)
    
    with torch.no_grad():
        for batch in progress_bar:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)
            
            # Forward pass
            outputs = model(input_ids, attention_mask, labels)
            loss = outputs['loss']
            
            # Track metrics
            total_loss += loss.item()
            predictions = outputs['logits'].argmax(dim=-1)
            confidences = outputs['probabilities'].max(dim=-1).values
            
            correct += (predictions == labels).sum().item()
            total += labels.size(0)
            
            # Store for detailed analysis
            all_predictions.extend(predictions.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_confidences.extend(confidences.cpu().numpy())
    
    epoch_loss = total_loss / len(test_loader)
    epoch_acc = 100.0 * correct / total
    
    # TensorBoard logging
    if writer is not None and epoch is not None:
        writer.add_scalar('Test/Loss', epoch_loss, epoch)
        writer.add_scalar('Test/Accuracy', epoch_acc, epoch)
    
    return epoch_loss, epoch_acc


def train(
    model: nn.Module,
    train_loader,
    test_loader,
    optimizer,
    scheduler,
    device: torch.device,
    num_epochs: int,
    save_dir: Path,
    patience: int = 2,
    writer: SummaryWriter = None
) -> dict:
    """
    Train model with early stopping.
    
    Returns:
        Training history dictionary
    """
    best_test_acc = 0.0
    best_epoch = 0
    epochs_without_improvement = 0
    
    history = {
        'train_loss': [],
        'train_acc': [],
        'test_loss': [],
        'test_acc': []
    }
    
    print(f"\n{'='*60}")
    print(f"Starting training on device: {device}")
    print(f"{'='*60}\n")
    
    for epoch in range(num_epochs):
        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, device, epoch, writer
        )
        
        # Evaluate
        test_loss, test_acc = evaluate(
            model, test_loader, device, epoch, writer
        )
        
        # Store history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['test_loss'].append(test_loss)
        history['test_acc'].append(test_acc)
        
        # Print epoch summary
        print(f"\nEpoch {epoch+1}/{num_epochs}:")
        print(f"  Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        print(f"  Test Loss:  {test_loss:.4f}, Test Acc:  {test_acc:.2f}%")
        
        # Save best model
        if test_acc > best_test_acc:
            best_test_acc = test_acc
            best_epoch = epoch
            epochs_without_improvement = 0
            
            # Save checkpoint
            checkpoint_path = save_dir / 'best_model.pt'
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'test_acc': test_acc,
                'test_loss': test_loss,
            }, checkpoint_path)
            print(f"  ✓ Saved best model (acc: {test_acc:.2f}%)")
        else:
            epochs_without_improvement += 1
            print(f"  No improvement for {epochs_without_improvement} epoch(s)")
        
        # Early stopping
        if epochs_without_improvement >= patience:
            print(f"\n⚠ Early stopping triggered after {epoch+1} epochs")
            break
    
    print(f"\n{'='*60}")
    print(f"Training completed!")
    print(f"Best test accuracy: {best_test_acc:.2f}% (epoch {best_epoch+1})")
    print(f"{'='*60}\n")
    
    return history


def main():
    parser = argparse.ArgumentParser(description='Train BERT transaction categorizer')
    parser.add_argument(
        '--data',
        type=Path,
        default=Path('data/datasets/features_prod.csv'),
        help='Path to features CSV'
    )
    parser.add_argument(
        '--model-name',
        type=str,
        default='bert-base-uncased',
        help='HuggingFace model name'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=5,
        help='Number of epochs'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Batch size'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=2e-5,
        help='Learning rate'
    )
    parser.add_argument(
        '--patience',
        type=int,
        default=2,
        help='Early stopping patience'
    )
    parser.add_argument(
        '--save-dir',
        type=Path,
        default=Path('models/bert_transaction_categorizer'),
        help='Directory to save model'
    )
    parser.add_argument(
        '--no-class-weights',
        action='store_true',
        help='Disable class weighting'
    )
    parser.add_argument(
        '--freeze-bert',
        action='store_true',
        help='Freeze BERT layers (train only classifier head)'
    )
    
    args = parser.parse_args()
    
    # Create save directory
    args.save_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup device (MPS for Apple Silicon, CUDA for NVIDIA, CPU fallback)
    if torch.backends.mps.is_available():
        device = torch.device('mps')
        print(f"✓ Using MPS (Apple Silicon GPU)")
    elif torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"✓ Using CUDA GPU")
    else:
        device = torch.device('cpu')
        print(f"⚠ Using CPU (training will be slower)")
    
    # Create dataloaders
    print(f"\nLoading data...")
    train_loader, test_loader, label_to_idx, idx_to_label, tokenizer = create_dataloaders(
        args.data,
        model_name=args.model_name,
        batch_size=args.batch_size
    )
    
    num_labels = len(label_to_idx)
    print(f"\nNumber of categories: {num_labels}")
    
    # Compute class weights
    class_weights = None
    if not args.no_class_weights:
        from collections import Counter
        train_labels = []
        for batch in train_loader:
            train_labels.extend(batch['labels'].tolist())
        label_counts = Counter(train_labels)
        
        # Convert to label string counts
        label_str_counts = Counter()
        for label_idx, count in label_counts.items():
            label_str_counts[idx_to_label[label_idx]] = count
        
        class_weights = compute_class_weights(label_str_counts, label_to_idx)
        class_weights = class_weights.to(device)
    
    # Create model
    print(f"\nCreating model...")
    model = create_model(
        num_labels=num_labels,
        model_name=args.model_name,
        use_class_weights=(class_weights is not None),
        class_weights=class_weights,
        freeze_bert=args.freeze_bert
    )
    model = model.to(device)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    # Setup optimizer
    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    
    # Setup learning rate scheduler
    total_steps = len(train_loader) * args.epochs
    warmup_steps = total_steps // 10  # 10% warmup
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )
    
    # Setup TensorBoard
    log_dir = args.save_dir / f'runs/{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    writer = SummaryWriter(log_dir=log_dir)
    print(f"TensorBoard logs: {log_dir}")
    
    # Train
    history = train(
        model=model,
        train_loader=train_loader,
        test_loader=test_loader,
        optimizer=optimizer,
        scheduler=scheduler,
        device=device,
        num_epochs=args.epochs,
        save_dir=args.save_dir,
        patience=args.patience,
        writer=writer
    )
    
    # Save label mappings
    mappings = {
        'label_to_idx': label_to_idx,
        'idx_to_label': idx_to_label,
        'num_labels': num_labels,
        'model_name': args.model_name
    }
    with (args.save_dir / 'label_mappings.json').open('w') as f:
        json.dump(mappings, f, indent=2)
    
    # Save training history
    with (args.save_dir / 'training_history.json').open('w') as f:
        json.dump(history, f, indent=2)
    
    writer.close()
    
    print(f"\n✓ Training complete!")
    print(f"  Model saved to: {args.save_dir / 'best_model.pt'}")
    print(f"  Mappings saved to: {args.save_dir / 'label_mappings.json'}")
    print(f"  History saved to: {args.save_dir / 'training_history.json'}")


if __name__ == '__main__':
    main()

