# Project Status

## Summary
- S3 sync tool updated to write a deterministic manifest with file inventory.
- Run indexer implemented and successfully generated `data/index/runs.jsonl` and `data/index/runs_summary.json`.
- Dataset builder implemented with whitelist enforcement, affordability label joins, uncategorised fallback, and persona-based train/test splits.
- Persona analyzer implemented to identify unique test profiles and assign train/test splits.
- SubClass mapper created for analysis purposes (SubClass not used in production training).
- **BS category mapper** created to learn bankstatements.com.au → BASIQ group mappings for fallback.
- **Feature extractor revised** to exclude BASIQ-only features (SubClass, ANZSIC) and produce production-ready features.
- **✅ BERT model trained** with 85.26% test accuracy (3 epochs, early stopping).
- **✅ Inference pipeline** implemented with 3-tier fallback (model → BS mapping → uncategorized).
- Examples added for transaction parsing and manifest generation; README updated with the PRP-001 workflow.

## Current Outputs

### Core Datasets
- **`data/index/runs.jsonl`**: Index of 36 runs from 3 unique personas (Max, Gilfoyle, Whistler)
- **`data/index/runs_summary.json`**: Summary statistics of indexed runs
- **`data/datasets/tx_labeled.csv`**: 22,457 labeled transactions with BASIQ group codes
- **`data/datasets/run_splits.json`**: Persona-based train/test split (Whistler+Gilfoyle=test, Max=train)
- **`data/reports/persona_analysis.json`**: Persona distribution and recommended splits

### Production-Ready Features
- **`data/datasets/features_prod.csv`**: 22,457 transactions with production-ready features
  - **Included**: description, amount, date, temporal features (day_of_week, month, etc.), amount_bucket
  - **Excluded**: SubClass (BASIQ-only), ANZSIC (BASIQ-only), enrich (BASIQ-only)
  - **Added**: bs_category, bs_fallback_group, bs_fallback_confidence
- **`data/datasets/bs_category_mappings.json`**: 27 bankstatements.com.au category → BASIQ group mappings
  - 17 semantic mappings (50% confidence)
  - 10 fallback mappings (30% confidence)

### Trained Model
- **`models/bert_transaction_categorizer/best_model.pt`**: Fine-tuned BERT model (1.2GB)
  - **Model**: bert-base-uncased (110M parameters)
  - **Training**: 3 epochs with early stopping
  - **Train Accuracy**: 94.44% (21,853 samples)
  - **Test Accuracy**: 85.26% (604 samples)
  - **Training Time**: ~30 minutes on Apple Silicon M-series
  - **Device**: MPS (Apple Silicon GPU acceleration)
  - **Class Weighting**: Enabled (handles imbalanced dataset)
- **`models/bert_transaction_categorizer/label_mappings.json`**: 29 active BASIQ categories
- **`models/bert_transaction_categorizer/training_history.json`**: Training metrics per epoch
- **`models/bert_transaction_categorizer/evaluation_results.json`**: Detailed evaluation metrics

### Analysis Artifacts
- **`data/datasets/subclass_mappings.json`**: SubClass → BASIQ group mappings (analysis only, NOT for training)
- **`data/reports/label_coverage.json`**: Label source distribution and coverage statistics
- **`data/reports/reconciliation.json`**: Data quality and reconciliation report

## Production Feature Strategy

### Key Insight: SubClass is BASIQ-Only
**Problem**: The SubClass field is assigned by BASIQ's internal API and won't be available when processing bankstatements.com.au data in production.

**Solution**: Train the model using ONLY features available in both BASIQ and bankstatements.com.au data:
- ✅ `description` (transaction text)
- ✅ `amount` (numeric value)
- ✅ `transaction_date`, `post_date` (temporal)
- ✅ Derived features: `day_of_week`, `day_of_month`, `month`, `year`, `amount_bucket`
- ✅ `direction` (CREDIT/DEBIT inferred from amount sign)

### Fallback Strategy
When model confidence is low (<90%), fall back to bankstatements.com.au category mapping:
1. **Model prediction** (primary): Trained on description + amount + date
2. **BS category fallback** (secondary): Use learned BS → BASIQ mappings
3. **Uncategorized fallback** (last resort): EXP-039 / INC-007

### Training Data Split
- **Train**: Max Wentworth-Smith persona (21,853 transactions)
- **Test**: Whistler Smith + Gilfoyle Bertram personas (604 transactions)
- **Strategy**: Persona-based to prevent data leakage (same person's transactions never in both train and test)

## Recommended Next Steps
1. ✅ **Model is production-ready!** (85.26% test accuracy achieved)
2. Test model on real bankstatements.com.au data in production
3. Collect data from the remaining 5 test profiles to expand the dataset
4. Monitor model performance and retrain if accuracy degrades
5. Consider data augmentation for rare categories (EXP-025, EXP-039)
6. Build REST API wrapper for the inference pipeline

## Model Performance Details

### Overall Metrics
- **Accuracy**: 85.26% on held-out test set (Whistler + Gilfoyle personas)
- **Confidence Distribution**:
  - High (≥0.9): 48.7% of predictions
  - Medium (0.7-0.9): 42.5% of predictions
  - Low (0.5-0.7): 6.1% of predictions
  - Very Low (<0.5): 2.6% of predictions
- **Mean Confidence**: 0.874

### Top Performing Categories
- EXP-013 (Transfers): 100% F1-score
- EXP-015 (Banking & Financial): 100% F1-score  
- EXP-007 (Cash): 95.8% F1-score
- EXP-041 (Fuel): 94.4% F1-score

### Common Errors
- EXP-039 (Uncategorized) → EXP-008 (Dining): 13 cases
- EXP-025 (Home Improvement) → EXP-035 (Subscriptions): 9 cases

## Usage Examples

### Training
```bash
cd /Users/marcuskorff/transformer
python3 transformer/training/train.py --epochs 5 --batch-size 16
```

### Evaluation
```bash
python3 transformer/training/evaluate.py
```

### Inference (Command Line)
```bash
python3 transformer/inference/predictor.py \
  --description "WOOLWORTHS SYDNEY AU" \
  --amount -85.50 \
  --bs-category "Groceries"
```

### Inference (Python API)
```python
from pathlib import Path
from transformer.inference.predictor import TransactionCategorizer

# Initialize
categorizer = TransactionCategorizer(
    model_dir=Path('models/bert_transaction_categorizer'),
    bs_mappings_path=Path('data/datasets/bs_category_mappings.json'),
    confidence_threshold=0.9
)

# Single prediction
category, confidence, source = categorizer.predict(
    description="NETFLIX.COM SUBSCRIPTION",
    amount=-19.99,
    bs_category="Online Retail and Subscription Services"
)
# Returns: ('EXP-035', 0.969, 'model')

# Batch prediction
transactions = [
    {'description': 'WOOLWORTHS SYDNEY', 'amount': -85.50},
    {'description': 'SALARY PAYMENT', 'amount': 5000.00},
]
results = categorizer.predict_batch(transactions)
```

