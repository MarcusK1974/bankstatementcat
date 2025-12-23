#!/usr/bin/env python3
"""
BERT Classifier for Transaction Categorization

Fine-tunes BERT for classifying transactions into 70 BASIQ categories.
"""

from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn
from transformers import BertModel, BertConfig


class BERTTransactionClassifier(nn.Module):
    """
    BERT-based transaction classifier.
    
    Architecture:
    - Pre-trained BERT encoder
    - Dropout layer
    - Linear classification head for 70 BASIQ categories
    """
    
    def __init__(
        self,
        model_name: str = 'bert-base-uncased',
        num_labels: int = 70,
        dropout: float = 0.1,
        freeze_bert: bool = False
    ):
        super().__init__()
        
        self.num_labels = num_labels
        
        # Load pre-trained BERT
        print(f"Loading pre-trained BERT: {model_name}")
        self.bert = BertModel.from_pretrained(model_name)
        
        # Optionally freeze BERT layers (faster training, might reduce accuracy)
        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False
            print("  BERT layers frozen (only training classification head)")
        else:
            print("  BERT layers unfrozen (full fine-tuning)")
        
        # Classification head
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_labels)
        
        # Initialize weights for classifier
        self.classifier.weight.data.normal_(mean=0.0, std=0.02)
        self.classifier.bias.data.zero_()
    
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        labels: torch.Tensor = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            input_ids: [batch_size, seq_length]
            attention_mask: [batch_size, seq_length]
            labels: [batch_size] (optional, for computing loss)
        
        Returns:
            Dictionary with 'logits', 'loss' (if labels provided), 'probabilities'
        """
        # BERT encoding
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        
        # Get [CLS] token representation
        pooled_output = outputs.pooler_output  # [batch_size, hidden_size]
        
        # Dropout and classification
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)  # [batch_size, num_labels]
        
        # Compute probabilities
        probabilities = torch.softmax(logits, dim=-1)
        
        # Compute loss if labels provided
        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits, labels)
        
        return {
            'logits': logits,
            'probabilities': probabilities,
            'loss': loss
        }
    
    def predict(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict categories and confidence scores.
        
        Args:
            input_ids: [batch_size, seq_length]
            attention_mask: [batch_size, seq_length]
        
        Returns:
            predictions: [batch_size] - predicted label indices
            confidences: [batch_size] - confidence scores (max probability)
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(input_ids, attention_mask)
            probabilities = outputs['probabilities']
            
            # Get predicted class and confidence
            confidences, predictions = torch.max(probabilities, dim=-1)
        
        return predictions, confidences


class BERTTransactionClassifierWeighted(BERTTransactionClassifier):
    """
    BERT classifier with weighted loss for handling class imbalance.
    """
    
    def __init__(
        self,
        model_name: str = 'bert-base-uncased',
        num_labels: int = 70,
        dropout: float = 0.1,
        freeze_bert: bool = False,
        class_weights: torch.Tensor = None
    ):
        super().__init__(model_name, num_labels, dropout, freeze_bert)
        
        # Register class weights as buffer (moves to device automatically)
        if class_weights is not None:
            self.register_buffer('class_weights', class_weights)
            print(f"  Using weighted loss (weight range: {class_weights.min():.3f} to {class_weights.max():.3f})")
        else:
            self.register_buffer('class_weights', None)
    
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        labels: torch.Tensor = None
    ) -> Dict[str, torch.Tensor]:
        """Forward pass with weighted loss."""
        # BERT encoding
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        
        # Get [CLS] token representation
        pooled_output = outputs.pooler_output
        
        # Dropout and classification
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        
        # Compute probabilities
        probabilities = torch.softmax(logits, dim=-1)
        
        # Compute weighted loss if labels provided
        loss = None
        if labels is not None:
            if self.class_weights is not None:
                loss_fn = nn.CrossEntropyLoss(weight=self.class_weights)
            else:
                loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits, labels)
        
        return {
            'logits': logits,
            'probabilities': probabilities,
            'loss': loss
        }


def create_model(
    num_labels: int,
    model_name: str = 'bert-base-uncased',
    use_class_weights: bool = True,
    class_weights: torch.Tensor = None,
    freeze_bert: bool = False,
    dropout: float = 0.1
) -> nn.Module:
    """
    Factory function to create BERT classifier.
    
    Args:
        num_labels: Number of output categories (70 for BASIQ)
        model_name: HuggingFace model name
        use_class_weights: Whether to use weighted loss
        class_weights: Class weights tensor (if use_class_weights=True)
        freeze_bert: Whether to freeze BERT layers (faster training)
        dropout: Dropout rate
    
    Returns:
        BERT classifier model
    """
    if use_class_weights:
        model = BERTTransactionClassifierWeighted(
            model_name=model_name,
            num_labels=num_labels,
            dropout=dropout,
            freeze_bert=freeze_bert,
            class_weights=class_weights
        )
    else:
        model = BERTTransactionClassifier(
            model_name=model_name,
            num_labels=num_labels,
            dropout=dropout,
            freeze_bert=freeze_bert
        )
    
    return model


if __name__ == '__main__':
    # Test model creation
    print("Testing BERT classifier...")
    
    # Create model
    model = create_model(num_labels=70, use_class_weights=False)
    
    # Test forward pass
    batch_size = 4
    seq_length = 128
    
    input_ids = torch.randint(0, 30522, (batch_size, seq_length))
    attention_mask = torch.ones(batch_size, seq_length)
    labels = torch.randint(0, 70, (batch_size,))
    
    print(f"\nTesting forward pass...")
    print(f"  Input shape: {input_ids.shape}")
    
    outputs = model(input_ids, attention_mask, labels)
    
    print(f"  Logits shape: {outputs['logits'].shape}")
    print(f"  Probabilities shape: {outputs['probabilities'].shape}")
    print(f"  Loss: {outputs['loss'].item():.4f}")
    
    # Test prediction
    predictions, confidences = model.predict(input_ids, attention_mask)
    print(f"\nPredictions: {predictions}")
    print(f"Confidences: {confidences}")
    
    print(f"\n✓ Model test successful")

