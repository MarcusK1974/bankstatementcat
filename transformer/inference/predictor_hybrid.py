#!/usr/bin/env python3
"""
Hybrid Learning Inference Pipeline

Implements 5-tier categorization with self-learning:
1. Internal transfer detection (95% conf)
2. Rule-based categorizer (if conf ≥ 95%)
3. Learned dictionary lookup (free, from Claude history)
4. Claude API (with learning, when uncertain)
5. BS fallback → Uncategorized (last resort)
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
from inference.transfer_detector import InternalTransferDetector
from inference.llm_categorizer import LLMCategorizer
from inference.learned_patterns import LearnedPatternsManager
from inference.claude_categorizer import ClaudeCategorizer
from config.api_config import get_config


class HybridTransactionCategorizer:
    """
    Hybrid self-learning transaction categorizer with 5-tier fallback.
    
    Features:
    - Internal transfer detection
    - Rule-based patterns (free)
    - Learned patterns dictionary (free, grows over time)
    - Claude API (paid, but learns)
    - BS fallback
    """
    
    def __init__(
        self,
        model_dir: Path,
        bs_mappings_path: Path,
        basiq_groups_path: Path,
        learned_patterns_path: Optional[Path] = None,
        device: str = 'auto',
        bert_confidence_threshold: float = 0.95,
        rule_confidence_threshold: float = 0.95,
        enable_transfer_detection: bool = True,
        enable_learning: bool = True,
        enable_claude: bool = True,
        test_mode: bool = False
    ):
        """
        Initialize hybrid categorizer.
        
        Args:
            model_dir: Directory containing trained BERT model
            bs_mappings_path: Path to BS category mappings JSON
            basiq_groups_path: Path to basiq_groups.yaml
            learned_patterns_path: Path to learned patterns JSON
            device: Device to run model on ('auto', 'mps', 'cuda', 'cpu')
            bert_confidence_threshold: Threshold for BERT predictions (default 0.95)
            rule_confidence_threshold: Threshold for rule-based predictions (default 0.95)
            enable_transfer_detection: Enable internal transfer detection
            enable_learning: Enable pattern learning from Claude
            enable_claude: Enable Claude API calls
            test_mode: Run in test mode (no real API calls)
        """
        self.bert_confidence_threshold = bert_confidence_threshold
        self.rule_confidence_threshold = rule_confidence_threshold
        self.enable_transfer_detection = enable_transfer_detection
        self.enable_learning = enable_learning
        self.enable_claude = enable_claude
        self.test_mode = test_mode
        
        # Load configuration
        config = get_config()
        
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
        
        # Initialize transfer detector
        self.transfer_detector: Optional[InternalTransferDetector] = None
        if self.enable_transfer_detection:
            self.transfer_detector = InternalTransferDetector()
            print("Transfer detector initialized")
        
        # Initialize rule-based LLM categorizer (free, keyword-based)
        self.llm_categorizer = LLMCategorizer(basiq_groups_path)
        print("Rule-based categorizer initialized")
        
        # Initialize learned patterns manager
        self.learned_patterns: Optional[LearnedPatternsManager] = None
        if self.enable_learning:
            if learned_patterns_path is None:
                learned_patterns_path = config.learned_patterns_path
            self.learned_patterns = LearnedPatternsManager(learned_patterns_path)
            print(f"Learned patterns manager initialized ({len(self.learned_patterns.patterns)} patterns)")
        
        # Initialize Claude API categorizer
        self.claude_categorizer: Optional[ClaudeCategorizer] = None
        if self.enable_claude:
            api_key = None if test_mode else config.anthropic_api_key
            self.claude_categorizer = ClaudeCategorizer(
                api_key=api_key,
                basiq_groups_path=basiq_groups_path,
                test_mode=test_mode
            )
            mode_str = "TEST MODE" if test_mode else "LIVE"
            print(f"Claude API categorizer initialized ({mode_str})")
    
    def train_transfer_detector(self, transactions: List[Dict]) -> None:
        """Train transfer detector on transaction patterns."""
        if self.transfer_detector and not self.transfer_detector._initialized:
            print("Training transfer detector...")
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
        Predict transaction category with 5-tier hybrid fallback.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            bs_category: Optional BS category
            third_party: Optional third party field
            account_number: Optional account number
            bsb: Optional BSB
        
        Returns:
            Tuple of (category, confidence, source)
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
        
        # Tier 2: Rule-based categorizer (simulated LLM, free)
        rule_prediction, rule_confidence, rule_reasoning = self.llm_categorizer.predict(
            description=description,
            amount=amount,
            bs_category=bs_category
        )
        
        if rule_prediction != 'UNKNOWN' and rule_confidence >= self.rule_confidence_threshold:
            # Check for uncategorized override
            if rule_prediction in ['EXP-039', 'INC-007']:
                bs_override = self._check_bs_override(bs_category)
                if bs_override:
                    return bs_override
            return rule_prediction, float(rule_confidence), 'llm'
        
        # Tier 3: Learned patterns dictionary (free, from Claude history)
        if self.enable_learning and self.learned_patterns:
            learned_pattern = self.learned_patterns.lookup(description)
            if learned_pattern:
                return learned_pattern.category, learned_pattern.confidence, 'learned'
        
        # Tier 4: Claude API (paid, but learns)
        if self.enable_claude and self.claude_categorizer:
            # Get similar patterns for consistency
            similar_patterns = []
            if self.learned_patterns:
                similar_patterns = self.learned_patterns.get_similar_patterns(description)
            
            claude_prediction, claude_confidence, claude_reasoning = self.claude_categorizer.predict(
                description=description,
                amount=amount,
                bs_category=bs_category,
                similar_patterns=similar_patterns
            )
            
            # Learn from Claude if enabled and confidence is high
            if self.enable_learning and self.learned_patterns:
                was_learned = self.learned_patterns.add_pattern(
                    description=description,
                    category=claude_prediction,
                    confidence=claude_confidence,
                    source='claude'
                )
                if was_learned:
                    # Save immediately to preserve learning
                    self.learned_patterns.save()
            
            # Check for uncategorized override
            if claude_prediction in ['EXP-039', 'INC-007']:
                bs_override = self._check_bs_override(bs_category)
                if bs_override:
                    return bs_override
            
            return claude_prediction, float(claude_confidence), 'claude'
        
        # Tier 5: BERT model (fallback if Claude disabled)
        bert_prediction, bert_confidence = self._predict_with_model(description)
        
        if bert_confidence >= self.bert_confidence_threshold:
            # Check for uncategorized override
            if bert_prediction in ['EXP-039', 'INC-007']:
                bs_override = self._check_bs_override(bs_category)
                if bs_override:
                    return bs_override
            return bert_prediction, float(bert_confidence), 'model'
        
        # Tier 6: BS category fallback
        if bs_category and bs_category in self.bs_mappings:
            mapping = self.bs_mappings[bs_category]
            basiq_group = mapping['basiq_group']
            bs_confidence = mapping['confidence']
            return basiq_group, bs_confidence, 'bs_fallback'
        
        # Final fallback: Uncategorized
        if amount < 0:
            return 'EXP-039', 0.3, 'uncategorized'
        else:
            return 'INC-007', 0.3, 'uncategorized'
    
    def _predict_with_model(self, description: str) -> Tuple[str, float]:
        """Get prediction from BERT model."""
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
        
        with torch.no_grad():
            predictions, confidences = self.model.predict(input_ids, attention_mask)
        
        pred_idx = predictions[0].item()
        confidence = confidences[0].item()
        predicted_label = self.idx_to_label.get(pred_idx, 'UNKNOWN')
        
        return predicted_label, confidence
    
    def _check_bs_override(self, bs_category: Optional[str]) -> Optional[Tuple[str, float, str]]:
        """Check if BS category should override an uncategorized prediction."""
        if not bs_category:
            return None
        
        ignore_categories = [
            'Uncategorised', 'Uncategorized', 'Other', 'Unknown',
            'All Other Credits', 'All Other Debits'
        ]
        
        if any(ignored in bs_category for ignored in ignore_categories):
            return None
        
        if bs_category in self.bs_mappings:
            mapping = self.bs_mappings[bs_category]
            basiq_group = mapping['basiq_group']
            
            if basiq_group not in ['EXP-039', 'INC-007']:
                bs_confidence = mapping['confidence']
                return basiq_group, bs_confidence, 'bs_override'
        
        return None
    
    def predict_batch(self, transactions: list[dict]) -> list[dict]:
        """Predict categories for a batch of transactions."""
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
    
    def save_learned_patterns(self) -> None:
        """Save learned patterns to disk."""
        if self.learned_patterns:
            self.learned_patterns.save()
            print(f"Saved {len(self.learned_patterns.patterns)} learned patterns")
    
    def get_statistics(self) -> Dict:
        """Get system statistics."""
        stats = {}
        
        if self.learned_patterns:
            stats['learned_patterns'] = self.learned_patterns.get_statistics()
        
        if self.claude_categorizer:
            stats['claude_api'] = self.claude_categorizer.get_statistics()
        
        return stats


# Alias for backwards compatibility
TransactionCategorizer = HybridTransactionCategorizer

