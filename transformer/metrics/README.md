# Enrichment Metrics Engine

A comprehensive metrics calculation system that processes categorized bank transactions to generate 46 enrichment metrics for credit assessment.

## Overview

The Enrichment Metrics Engine calculates financial metrics based on categorized bank statement transactions (BASIQ groups). These metrics are designed for credit assessment and provide insights into:

- Income stability and sources
- Spending patterns (discretionary vs non-discretionary)
- Financial commitments and debt obligations
- Government benefit reliance
- Risk indicators and red flags

## Metrics Categories

### Expenses (7 metrics)
- **ME012**: Monthly spend on non-discretionary expenses (money)
- **ME013**: % of spend on non-discretionary expenses (percent)
- **ME014**: Monthly spend on discretionary expenses (money)
- **ME015**: % of spend on discretionary expenses (percent)
- **ME016**: Monthly spend on other expenses (money)
- **ME034**: Average Outgoings monthly (money)
- **ME039**: Average outgoings excluding liabilities (money)

### Income Sources (11 metrics)
- **ME001**: # of identified salary sources (integer)
- **ME002**: Average monthly amount from salary (money)
- **ME003**: Salary has been stable for (months) (integer)
- **ME004**: Other possible income monthly (money)
- **ME033**: Average Income monthly - **SALARY ONLY** (money)
- **ME035**: Total Income has been stable for (months) - salary stability (integer)
- **ME036**: Median monthly amount from Salary (money)
- **ME037**: Median Income monthly - **SALARY ONLY** (money)
- **ME040**: Average Monthly Credits - **ALL INCOME** (money)
- **ME041**: Average Monthly Debits (money)
- **ME042**: # of recent income sources (integer)
- **ME043**: # of ongoing regular income sources (integer)
- **ME045**: Total Income has been secure for (months) - all income (integer)

### Financial Commitments (6 metrics)
- **ME008**: Average monthly amount to lenders (money)
- **ME009**: # of identified lending companies (integer)
- **ME010**: Total credit card limit (money) - requires account data
- **ME011**: Total credit card balance (money) - requires account data
- **ME046**: Average monthly ongoing amount to lenders (money)
- **ME048**: Ongoing Monthly Mortgage Repayment (money)

### Government Services (3 metrics)
- **ME005**: Youth Allowance monthly (money)
- **ME006**: Rental Assistance monthly (money)
- **ME007**: Misc Government services monthly (money)

### Risk Flags (12 metrics)
- **ME022**: Has recent changes to salary circumstances (boolean)
- **ME023**: Has received crisis support payments (boolean)
- **ME024**: Has superannuation credits (boolean)
- **ME025**: Has cash advances (boolean)
- **ME026**: Has redraws (boolean)
- **ME027**: Has High-Cost Finance (boolean)
- **ME028**: Missing non-discretionary expenses: groceries (boolean)
- **ME029**: Missing non-discretionary expenses: telecommunication (boolean)
- **ME030**: Missing non-discretionary expenses: utilities (boolean)
- **ME031**: Has Unemployment Benefit (boolean)
- **ME032**: Receives Child Support (boolean)
- **ME047**: Has unshared mortgage account (boolean)

### Risk Metrics (5 metrics)
- **ME017**: # of SACC loans (integer)
- **ME018**: % of income withdrawn via ATM (percent)
- **ME019**: # of financial dishonours (integer)
- **ME020**: % of income spent on High Risk Activities (percent)
- **ME021**: Total spend on High Risk Activities (money)

## Usage

### Single Customer

```bash
python tools/calculate_metrics.py \
  --input data/output/customer_categorized.csv \
  --output results/customer_metrics.json
```

### Batch Processing

```bash
python tools/calculate_metrics.py \
  --batch data/output/ \
  --output-csv results/all_metrics.csv \
  --output-json results/all_metrics.json
```

### Export Metrics Schema

```bash
python tools/calculate_metrics.py \
  --export-schema docs/metrics_schema.json
```

## Input Format

The input CSV must have categorized transactions with these columns:
- `date` (DD/MM/YYYY format)
- `description` (transaction description)
- `amount` (positive for income, negative for expenses)
- `basiq_category` or `basiq_category_code` (BASIQ group code, e.g., INC-009, EXP-016)

Example:
```csv
date,description,amount,balance,bs_category,basiq_category
01/07/2024,TECH STARTUP PTY LTD SALARY,4200.0,5200.0,Salary,INC-009
05/07/2024,WOOLWORTHS METRO,−45.0,5155.0,Groceries,EXP-016
```

## Output Formats

### JSON Output
```json
{
  "customer_id": "persona1",
  "reporting_period_days": 180,
  "calculation_date": "2024-12-24T10:30:00",
  "ME033": 8400.00,
  "ME034": 3011.16,
  "ME027": true,
  ...
}
```

### CSV Output
One row per customer with all 46 metrics as columns.

## Configuration

### Reporting Period
Default: 180 days (6 months)

Configurable in `transformer/config/metrics_config.yaml`:
```yaml
reporting_period_days: 180
```

### Expense Classification
Discretionary vs non-discretionary expenses follow HEM (Household Expenditure Measure) principles.

Defined in `transformer/config/expense_classification.yaml`:
- **Non-discretionary**: Groceries, utilities, rent, telecommunications, medical, education
- **Discretionary**: Dining out, entertainment, alcohol, retail, travel

### Stability Detection
- **Stable**: Monthly amount within ±10% of previous month
- **Secure**: Monthly amount stable or increasing
- **Recent**: Last 2 months from reporting period end

## Key Concepts

### ME033 vs ME040
- **ME033** (Average Income monthly) = **SALARY ONLY** (INC-009)
- **ME040** (Average Monthly Credits) = **ALL INCOME SOURCES**

ME033 represents "working income" while ME040 represents total credits including government benefits, pensions, etc.

### Frequency Detection
The system automatically detects transaction frequencies:
- **Weekly**: 3-9 days apart
- **Fortnightly**: 10-17 days apart (26 payments/year)
- **Monthly**: 25-35 days apart

Requires minimum 3 occurrences to confirm pattern.

### High-Risk Activities
Includes:
- ATM withdrawals (EXP-001)
- Cash advances from credit cards (EXP-003)
- Gambling (EXP-014)
- Credit card interest (EXP-006)
- Mortgage redraws (EXP-029)

### High-Cost Finance
Includes:
- Small Amount Credit Contracts / SACC (EXP-033)
- BNPL providers (also EXP-033)
- Peer-to-peer finance (EXP-026)
- Other finance (EXP-025)

## Architecture

```
MetricsEngine
├── ExpenseCalculator (ME012-ME016, ME034, ME039)
├── IncomeCalculator (ME001-ME004, ME033, ME035-ME037, ME040-ME043, ME045)
├── FinancialCommitmentsCalculator (ME008-ME011, ME046, ME048)
├── GovernmentServicesCalculator (ME005-ME007)
├── RiskFlagsCalculator (ME022-ME032, ME047)
└── RiskMetricsCalculator (ME017-ME021)
```

Each calculator extends `BaseCalculator` which provides common utilities:
- Date range filtering
- Calendar month aggregation
- Stability detection
- Frequency detection
- Merchant counting

## Testing

Test with the 6 synthetic personas:

```bash
# Categorize test personas first
python -c "from transformer.inference.predictor_final import FinalTransactionCategorizer; ..."

# Calculate metrics
python tools/calculate_metrics.py \
  --batch data/output/ \
  --output-csv results/test_metrics.csv
```

**Test Personas:**
1. Young Professional with BNPL ($8,400 salary, 2 BNPL lenders)
2. Family with Kids (mortgage, childcare, FTB benefits)
3. Retiree (pension, super credits, medical expenses)
4. Student (Youth Allowance, Rent Assistance, part-time work)
5. Financial Stress (Jobseeker, SACC loans, 20 dishonours, collection agencies)
6. High Earner ($17,800 salary, rental income, investments)

## Known Limitations

1. **ME010/ME011** require shared credit card account data (limits/balances)
   - Returns `null` if account data not provided
   
2. **Income vs Expense Detection**: The categorizer doesn't use transaction direction
   - Positive amounts like "WOOLWORTHS WAGES" may be categorized as EXP-016 (Groceries) instead of INC-009 (Salary)
   - Metrics calculator works correctly based on amount sign, but input categorization should be improved

3. **Calendar Month Normalization**: All months normalized to 30 days
   - 10% tolerance for "stable" determination
   - Handles fortnightly pay (26 payments/year)

## Dependencies

- pandas
- numpy
- pyyaml

## Files

```
transformer/
├── config/
│   ├── expense_classification.yaml    # HEM-based expense classification
│   └── metrics_config.yaml             # Calculation parameters
├── metrics/
│   ├── __init__.py
│   ├── base_calculator.py              # Common utilities
│   ├── expense_calculator.py           # 7 expense metrics
│   ├── income_calculator.py            # 11 income metrics
│   ├── financial_commitments_calculator.py  # 6 financial metrics
│   ├── government_services_calculator.py    # 3 govt benefit metrics
│   ├── risk_flags_calculator.py        # 12 boolean flags
│   ├── risk_metrics_calculator.py      # 5 risk metrics
│   └── metrics_engine.py               # Main orchestrator
tools/
└── calculate_metrics.py                # CLI tool
```

## Production Integration

For integration with credit platforms:

```python
from transformer.metrics import MetricsEngine

# Initialize
engine = MetricsEngine()

# Calculate metrics
metrics = engine.calculate_all_metrics(
    transactions_df=transactions,
    customer_id="CUST123",
    account_data={
        'credit_card_limits': [5000, 10000],
        'credit_card_balances': [2300, 4500],
        'has_mortgage_account': True
    }
)

# Export to API
api_client.post_metrics(metrics)
```

## Support

For issues or questions, refer to:
- Metrics definitions: `Metrics.docx`
- BASIQ taxonomy: `Groups.docx` or `docs/basiq_groups.yaml`
- Configuration files: `transformer/config/`

