# Claude API Setup Guide

The hybrid categorization system requires a Claude API key to handle unknown merchants. Here's how to set it up:

## Quick Setup (2 minutes)

### Step 1: Get Your API Key

1. Go to: https://console.anthropic.com/
2. Sign up or log in with your account
3. Navigate to "API Keys" section
4. Click "Create Key"
5. Copy the key (it starts with `sk-ant-`)

**Your key will look like:** `sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Step 2: Configure the System

**Choose ONE method:**

#### Method A: Environment Variable (Quick)
```bash
export ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

#### Method B: .env File (Persistent)
```bash
# Create .env file
cp env.example .env

# Edit .env and set your key:
nano .env  # or use any text editor

# Add this line (replace with your actual key):
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

### Step 3: Verify Setup

```bash
python3 -c "from transformer.config.api_config import get_config; print(get_config().get_summary())"
```

Expected output:
```
{
  'has_api_key': True,
  'api_key_prefix': 'sk-ant-api',
  'claude_confidence_threshold': 0.95,
  'learning_enabled': True,
  'learned_patterns_path': 'data/learned_patterns.json',
  'test_mode': False
}
```

## How It Works

The system uses a **5-tier categorization approach**:

1. **Internal Transfer Detection** (FREE)
   - Detects transfers between accounts
   
2. **Rule-Based Categorization** (FREE)
   - 190 Australian brand rules
   - Payment pattern recognition (Square, Ezidebit, etc.)
   - Keyword inference (ORTHO→Medical, UNI→Education)
   - Covers ~31% of transactions
   
3. **Learned Patterns Dictionary** (FREE)
   - Cached Claude responses from previous runs
   - Covers ~69% of transactions after initial learning
   - No API calls needed!
   
4. **Claude API** (PAID - only for new merchants)
   - Only called for truly unknown merchants
   - ~0.2% of transactions (2 out of 930 in tests)
   - Cost: ~$0.0004 per 930 transactions
   
5. **Fallback** (FREE)
   - Uses bankstatements.com.au category if available

## Cost Expectations

Based on 930 NAB credit card transactions:

| Week | Transactions | Claude Calls | Cost/Day | Notes |
|------|--------------|--------------|----------|-------|
| 1    | 1000/day    | ~100         | $0.02    | Building pattern library |
| 4    | 1000/day    | ~50          | $0.01    | 50% patterns learned |
| 12   | 1000/day    | ~20          | $0.004   | 80% patterns learned |
| 52   | 1000/day    | ~5           | $0.001   | 95% patterns learned |

**Annual cost at 1000 applications/day: ~$2-3**

The system becomes cheaper over time as it learns!

## Test Mode (No API Charges)

To test the system without making real API calls:

```bash
export TEST_MODE=true
```

Or in `.env`:
```
TEST_MODE=true
```

This simulates API calls without charges, useful for:
- Development
- Testing
- Demos

## Configuration Options

Edit `.env` or set environment variables:

```bash
# API Key (required)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Confidence threshold for categorization (0.0-1.0)
CLAUDE_CONFIDENCE_THRESHOLD=0.95

# Enable/disable learning from Claude
LEARNING_ENABLED=true

# Path to learned patterns file
LEARNED_PATTERNS_PATH=data/learned_patterns.json

# Test mode (simulate API calls)
TEST_MODE=false
```

## Troubleshooting

### "No valid ANTHROPIC_API_KEY found"

**Solution:**
```bash
# Check if key is set
echo $ANTHROPIC_API_KEY

# If empty, set it:
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or create .env file (see Method B above)
```

### "API key not working"

**Check:**
1. Key starts with `sk-ant-`
2. No extra spaces or quotes
3. Key is active in Claude console: https://console.anthropic.com/

### "Module 'dotenv' not found"

**Solution:**
```bash
pip install python-dotenv
```

### "Import error: anthropic"

**Solution:**
```bash
pip install anthropic
```

## Security Best Practices

✅ **DO:**
- Use environment variables or `.env` file
- Add `.env` to `.gitignore` (already done)
- Rotate API keys periodically
- Use separate keys for dev/prod

❌ **DON'T:**
- Commit API keys to git
- Share keys in Slack/email
- Use the same key across projects
- Hardcode keys in scripts

## Need Help?

- **API Documentation:** https://docs.anthropic.com/
- **Pricing:** https://www.anthropic.com/api#pricing  
- **Support:** https://support.anthropic.com/
- **Project README:** [README.md](README.md)
- **Hybrid System Guide:** [HYBRID_SETUP_GUIDE.md](HYBRID_SETUP_GUIDE.md)

## Quick Start Example

Once configured, categorize transactions:

```python
from pathlib import Path
from transformer.inference.predictor_hybrid import HybridTransactionCategorizer

# Initialize (API key loaded automatically from environment)
categorizer = HybridTransactionCategorizer(
    model_dir=Path('models/bert_transaction_categorizer_v3'),
    bs_mappings_path=Path('data/datasets/bs_category_mappings.json'),
    basiq_groups_path=Path('docs/basiq_groups.yaml'),
    enable_claude=True,
    enable_learning=True
)

# Categorize a transaction
category, confidence, source = categorizer.predict(
    description="WOOLWORTHS 551 ASHWOOD",
    amount=-45.50,
    bs_category="Groceries"
)

print(f"Category: {category}")  # EXP-016
print(f"Confidence: {confidence}")  # 0.97
print(f"Source: {source}")  # llm (rule-based, FREE!)
```

🎉 **That's it!** The system is ready to categorize transactions.

