#!/usr/bin/env python3
"""
Inference Pipeline for BERT Transaction Categorizer

Implements 4-tier fallback strategy:
1. Internal transfer detection (returns early)
2. LLM reasoning (high confidence threshold)
3. BERT model prediction (medium confidence threshold)
4. BankStatements category mapping → Uncategorized (last resort)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import torch
from transformers import BertTokenizer

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from training.bert_classifier import create_model
from inference.transfer_detector import InternalTransferDetector, create_detector
from inference.llm_categorizer import LLMCategorizer, create_categorizer


class TransactionCategorizer:
    """
    Production-ready transaction categorizer with 4-tier fallback.
    """
    
    def __init__(
        self,
        model_dir: Path,
        bs_mappings_path: Path,
        basiq_groups_path: Path,
        device: str = 'auto',
        bert_confidence_threshold: float = 0.8,
        llm_confidence_threshold: float = 0.9,
        enable_transfer_detection: bool = True,
        enable_llm: bool = True
    ):
        """
        Initialize categorizer with all tiers.
        
        Args:
            model_dir: Directory containing trained model
            bs_mappings_path: Path to BS category mappings JSON
            basiq_groups_path: Path to basiq_groups.yaml
            device: Device to run model on ('auto', 'mps', 'cuda', 'cpu')
            bert_confidence_threshold: Threshold for BERT predictions (default 0.8)
            llm_confidence_threshold: Threshold for LLM predictions (default 0.9)
            enable_transfer_detection: Enable internal transfer detection
            enable_llm: Enable LLM reasoning layer
        """
        self.bert_confidence_threshold = bert_confidence_threshold
        self.llm_confidence_threshold = llm_confidence_threshold
        self.enable_transfer_detection = enable_transfer_detection
        self.enable_llm = enable_llm
        
        # Setup device
        if device == 'auto':
            if torch.backends.mps.is_available():
                self.device = torch.device('mps')
            elif torch.cuda.is_available():
                self.device = torch.device('cuda')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)
        
        print(f"Device: {self.device}")
        
        # Load label mappings
        with (model_dir / 'label_mappings.json').open() as f:
            mappings = json.load(f)
        
        self.label_to_idx = {k: int(v) for k, v in mappings['label_to_idx'].items()}
        self.idx_to_label = {int(k): v for k, v in mappings['idx_to_label'].items()}
        self.model_name = mappings['model_name']
        
        # Load tokenizer
        print(f"Loading tokenizer: {self.model_name}")
        self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
        
        # Load BERT model
        print(f"Loading model from: {model_dir / 'best_model.pt'}")
        num_labels = len(self.label_to_idx)
        self.model = create_model(
            num_labels=num_labels,
            model_name=self.model_name,
            use_class_weights=True,
            class_weights=torch.zeros(num_labels)
        )
        
        checkpoint = torch.load(model_dir / 'best_model.pt', map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model = self.model.to(self.device)
        self.model.eval()
        
        print(f"Model loaded (test acc: {checkpoint['test_acc']:.2f}%)")
        
        # Load BS category mappings
        with bs_mappings_path.open() as f:
            bs_data = json.load(f)
            self.bs_mappings = bs_data.get('mappings', {})
        
        print(f"Loaded {len(self.bs_mappings)} BS category mappings")
        
        # Initialize transfer detector (will be trained on first batch)
        self.transfer_detector: Optional[InternalTransferDetector] = None
        if self.enable_transfer_detection:
            self.transfer_detector = InternalTransferDetector()
            print("Transfer detector initialized (will analyze patterns on first batch)")
        
        # Initialize LLM categorizer
        self.llm_categorizer: Optional[LLMCategorizer] = None
        if self.enable_llm:
            self.llm_categorizer = create_categorizer(basiq_groups_path)
            print("LLM categorizer initialized")
    
    def train_transfer_detector(self, transactions: List[Dict]) -> None:
        """
        Train transfer detector on a batch of transactions.
        
        Args:
            transactions: List of transaction dicts with full data
        """
        if self.transfer_detector and not self.transfer_detector._initialized:
            print("Training transfer detector on transaction patterns...")
            self.transfer_detector.analyze_transactions(transactions)
            user_accounts = self.transfer_detector.get_user_accounts()
            print(f"  Detected {len(user_accounts)} user account(s)")
    
    def predict(
        self,
        description: str,
        amount: float,
        bs_category: Optional[str] = None,
        third_party: Optional[str] = None,
        account_number: Optional[str] = None,
        bsb: Optional[str] = None
    ) -> Tuple[str, float, str]:
        """
        Predict transaction category with 4-tier fallback + uncategorized override.
        
        Args:
            description: Transaction description
            amount: Transaction amount (negative for expenses, positive for income)
            bs_category: Optional BankStatements.com.au category
            third_party: Optional third party field from BS
            account_number: Optional user account number
            bsb: Optional BSB
        
        Returns:
            Tuple of (predicted_category, confidence, source)
            where source is 'internal_transfer', 'llm', 'model', 'bs_fallback', 'bs_override', or 'uncategorized'
        """
        # Tier 1: Internal transfer detection
        if self.enable_transfer_detection and self.transfer_detector:
            is_internal = self.transfer_detector.is_internal_transfer(
                description=description,
                amount=amount,
                bs_category=bs_category,
                third_party=third_party
            )
            
            if is_internal:
                return 'EXP-013', 0.95, 'internal_transfer'
        
        # Tier 2: LLM reasoning
        if self.enable_llm and self.llm_categorizer:
            llm_prediction, llm_confidence, llm_reasoning = self.llm_categorizer.predict(
                description=description,
                amount=amount,
                bs_category=bs_category
            )
            
            if llm_prediction != 'UNKNOWN' and llm_confidence >= self.llm_confidence_threshold:
                # Uncategorized override: if LLM says uncategorized but BS has a specific category, use BS
                if llm_prediction in ['EXP-039', 'INC-007']:
                    bs_override = self._check_bs_override(bs_category)
                    if bs_override:
                        return bs_override
                return llm_prediction, float(llm_confidence), 'llm'
        
        # Tier 3: BERT model prediction
        bert_prediction, bert_confidence = self._predict_with_model(description)
        
        if bert_confidence >= self.bert_confidence_threshold:
            # Uncategorized override: if BERT says uncategorized but BS has a specific category, use BS
            if bert_prediction in ['EXP-039', 'INC-007']:
                bs_override = self._check_bs_override(bs_category)
                if bs_override:
                    return bs_override
            return bert_prediction, float(bert_confidence), 'model'
        
        # Tier 4: BS category fallback
        if bs_category and bs_category in self.bs_mappings:
            mapping = self.bs_mappings[bs_category]
            basiq_group = mapping['basiq_group']
            bs_confidence = mapping['confidence']
            return basiq_group, bs_confidence, 'bs_fallback'
        
        # Tier 5: Uncategorized fallback
        if amount < 0:
            return 'EXP-039', 0.3, 'uncategorized'  # Uncategorized expense
        else:
            return 'INC-007', 0.3, 'uncategorized'  # Uncategorized income
    
    def _check_bs_override(self, bs_category: Optional[str]) -> Optional[Tuple[str, float, str]]:
        """
        Check if BS category should override an uncategorized prediction.
        
        Args:
            bs_category: BankStatements.com.au category
        
        Returns:
            Tuple of (category, confidence, source) if override should happen, None otherwise
        """
        if not bs_category:
            return None
        
        # Ignore if BS itself says uncategorized or other generic terms
        ignore_categories = [
            'Uncategorised', 'Uncategorized', 'Other', 'Unknown',
            'All Other Credits', 'All Other Debits'
        ]
        
        if any(ignored in bs_category for ignored in ignore_categories):
            return None
        
        # Check if we have a mapping for this BS category
        if bs_category in self.bs_mappings:
            mapping = self.bs_mappings[bs_category]
            basiq_group = mapping['basiq_group']
            
            # Only override if the BS mapping itself isn't uncategorized
            if basiq_group not in ['EXP-039', 'INC-007']:
                bs_confidence = mapping['confidence']
                return basiq_group, bs_confidence, 'bs_override'
        
        return None
    
    def _predict_with_model(self, description: str) -> Tuple[str, float]:
        """
        Get prediction from BERT model.
        
        Returns:
            Tuple of (predicted_label, confidence)
        """
        # Tokenize
        encoding = self.tokenizer(
            description,
            add_special_tokens=True,
            max_length=128,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        
        # Predict
        with torch.no_grad():
            predictions, confidences = self.model.predict(input_ids, attention_mask)
        
        # Get label
        pred_idx = predictions[0].item()
        confidence = confidences[0].item()
        predicted_label = self.idx_to_label.get(pred_idx, 'UNKNOWN')
        
        return predicted_label, confidence
    
    def predict_batch(
        self,
        transactions: list[dict]
    ) -> list[dict]:
        """
        Predict categories for a batch of transactions.
        
        Args:
            transactions: List of transaction dicts with keys:
                - description (required)
                - amount (required)
                - bs_category (optional)
                - third_party (optional)
                - account_number (optional)
                - bsb (optional)
        
        Returns:
            List of prediction dicts with keys:
                - predicted_category
                - confidence
                - source
        """
        # Train transfer detector on first batch
        if self.enable_transfer_detection and self.transfer_detector and not self.transfer_detector._initialized:
            self.train_transfer_detector(transactions)
        
        results = []
        
        for tx in transactions:
            pred, conf, source = self.predict(
                description=tx['description'],
                amount=tx['amount'],
                bs_category=tx.get('bs_category'),
                third_party=tx.get('third_party'),
                account_number=tx.get('account_number'),
                bsb=tx.get('bsb')
            )
            
            results.append({
                'predicted_category': pred,
                'confidence': conf,
                'source': source
            })
        
        return results


def main():
    """Example usage of the categorizer."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Categorize transactions')
    parser.add_argument(
        '--model-dir',
        type=Path,
        default=Path('models/bert_transaction_categorizer_v3'),
        help='Directory containing trained model'
    )
    parser.add_argument(
        '--bs-mappings',
        type=Path,
        default=Path('data/datasets/bs_category_mappings.json'),
        help='Path to BS category mappings'
    )
    parser.add_argument(
        '--basiq-groups',
        type=Path,
        default=Path('docs/basiq_groups.yaml'),
        help='Path to BASIQ groups YAML'
    )
    parser.add_argument(
        '--description',
        type=str,
        help='Transaction description to categorize'
    )
    parser.add_argument(
        '--amount',
        type=float,
        default=-100.0,
        help='Transaction amount'
    )
    parser.add_argument(
        '--bs-category',
        type=str,
        default=None,
        help='BankStatements.com.au category (optional)'
    )
    parser.add_argument(
        '--disable-transfer-detection',
        action='store_true',
        help='Disable internal transfer detection'
    )
    parser.add_argument(
        '--disable-llm',
        action='store_true',
        help='Disable LLM reasoning'
    )
    
    args = parser.parse_args()
    
    # Create categorizer
    print("Initializing categorizer...")
    categorizer = TransactionCategorizer(
        model_dir=args.model_dir,
        bs_mappings_path=args.bs_mappings,
        basiq_groups_path=args.basiq_groups,
        bert_confidence_threshold=0.8,
        llm_confidence_threshold=0.9,
        enable_transfer_detection=not args.disable_transfer_detection,
        enable_llm=not args.disable_llm
    )
    
    if args.description:
        # Single prediction
        print(f"\nCategorizing transaction:")
        print(f"  Description: {args.description}")
        print(f"  Amount: ${args.amount:.2f}")
        if args.bs_category:
            print(f"  BS Category: {args.bs_category}")
        
        pred, conf, source = categorizer.predict(
            description=args.description,
            amount=args.amount,
            bs_category=args.bs_category
        )
        
        print(f"\nPrediction:")
        print(f"  Category: {pred}")
        print(f"  Confidence: {conf:.3f}")
        print(f"  Source: {source}")
    else:
        # Example batch prediction
        print(f"\nRunning example batch predictions...")
        
        examples = [
            {'description': 'WOOLWORTHS 1234 SYDNEY AU', 'amount': -85.50, 'bs_category': 'Groceries'},
            {'description': 'PAYMENT TO MOMENTUM ENERGY 23522784', 'amount': -167.23, 'bs_category': 'Utilities'},
            {'description': 'ANZ INTERNET BANKING BPAY TAX OFFICE PAYMENT', 'amount': -2124.0, 'bs_category': 'Tax'},
            {'description': 'SALARY PAYMENT', 'amount': 5000.00, 'bs_category': 'Wages'},
            {'description': 'ANZ M-BANKING FUNDS TFER TRANSFER 320927 FROM 655923834', 'amount': 2100.0, 'bs_category': 'Internal Transfer'},
        ]
        
        results = categorizer.predict_batch(examples)
        
        print(f"\n{'Description':<50} {'Amount':>10} {'Predicted':<10} {'Conf':>6} {'Source':<20}")
        print('-' * 110)
        for tx, result in zip(examples, results):
            desc = tx['description'][:47] + '...' if len(tx['description']) > 50 else tx['description']
            print(f"{desc:<50} ${tx['amount']:>9.2f} {result['predicted_category']:<10} "
                  f"{result['confidence']:>6.3f} {result['source']:<20}")


if __name__ == '__main__':
    main()
