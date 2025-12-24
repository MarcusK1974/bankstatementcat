# Synthetic Test Bank Statements

## Overview
This directory contains 6 synthetic bank statements designed to test the transaction categorization system. Each persona represents a different financial profile with realistic spending patterns.

## Test Personas

### 1. **Alex Chen - Young Professional with BNPL** (`persona1_young_professional_6month.csv`)
- **Profile**: 28yo tech worker, high BNPL usage
- **Income**: $4,200/fortnight salary
- **Key Features**:
  - Multiple BNPL accounts (Afterpay, Zip)
  - Subscription services (Netflix, Spotify)
  - Frequent dining out and food delivery
  - Online shopping (ASOS, The Iconic)
- **Test Focus**: BNPL detection (EXP-033), subscription recognition

### 2. **Sarah Johnson - Family with Kids** (`persona2_family_6month.csv`)
- **Profile**: 36yo council worker, family with 2 kids
- **Income**: $3,800/fortnight salary + $340/fortnight Family Tax Benefit
- **Key Features**:
  - Mortgage repayments
  - Childcare and school fees
  - Regular grocery shopping (Coles, Aldi)
  - Health and medical expenses
- **Test Focus**: Family Tax Benefit detection (INC-014), childcare (EXP-011)

### 3. **Robert Williams - Retiree** (`persona3_retiree_6month.csv`)
- **Profile**: 72yo retiree
- **Income**: Age Pension ($1,116/fortnight) + Super pension + Dividends
- **Key Features**:
  - Age pension payments (INC-018)
  - Superannuation credits (INC-010)
  - Medicare rebates (INC-015)
  - High medical expenses
- **Test Focus**: Pension detection, Medicare rebates, investment income

### 4. **Emma Davis - University Student** (`persona4_student_6month.csv`)
- **Profile**: 21yo university student, part-time work
- **Income**: Youth Allowance + Rent Assistance + Part-time wages
- **Key Features**:
  - Youth Allowance payments (INC-012)
  - Rental Assistance (INC-013)
  - Low-cost groceries (Aldi)
  - BNPL usage (Sezzle)
  - Public transport (Myki)
- **Test Focus**: Student benefits, low-income patterns

### 5. **Michael Brown - Financial Difficulties** (`persona5_financial_stress_6month.csv`)
- **Profile**: 45yo, unemployed, financial stress
- **Income**: Jobseeker payment only ($693/fortnight)
- **Key Features**:
  - Jobseeker payments (INC-016)
  - Collection agency payments (EXP-005) - **CRITICAL**
  - SACC loans (Nimble, Wallet Wizard) (EXP-033)
  - Dishonour fees (EXP-009) - **CRITICAL**
  - Gambling (EXP-014)
- **Test Focus**: Collection agencies, dishonours, SACC lenders - HIGH RISK INDICATORS

### 6. **Jennifer Lee - High Income Professional** (`persona6_high_earner_6month.csv`)
- **Profile**: 42yo investment banker, investment property owner
- **Income**: $8,900/fortnight salary + $2,400/month rental income + dividends
- **Key Features**:
  - High salary (INC-009)
  - Rental income (INC-008)
  - Investment income (INC-005)
  - Voluntary super contributions (EXP-034)
  - Charity donations (EXP-010)
  - Premium dining and travel
- **Test Focus**: Multiple income sources, high-value transactions

## File Format

Each persona has two files:

### 1. `personaX_6month.csv` (Bank Statement format - same as bankstatements.com.au)
```csv
date,description,amount,balance,bs_category
01/07/2024,TECH STARTUP PTY LTD SALARY,4200.0,5200.0,Salary
05/07/2024,RAY WHITE REAL ESTATE,-1800.0,3400.0,Rent
```

### 2. `personaX_6month_expected.csv` (With ground truth BASIQ categories)
```csv
date,description,amount,bs_category,expected_basiq
01/07/2024,TECH STARTUP PTY LTD SALARY,4200.0,Salary,INC-009
05/07/2024,RAY WHITE REAL ESTATE,-1800.0,Rent,EXP-030
```

## Test Coverage

### Critical Categories Tested:
- ✅ **EXP-005**: Collection Agencies (Persona 5 - Credit Corp)
- ✅ **EXP-009**: Dishonours (Persona 5 - Dishonour fees)
- ✅ **EXP-033**: Small Amount Lending - SACC & BNPL (Personas 1, 4, 5)
- ✅ **EXP-034**: Superannuation (Persona 6 - Voluntary contributions)
- ✅ **INC-008**: Rental Income (Persona 6)
- ✅ **INC-012**: Youth Allowance (Persona 4)
- ✅ **INC-013**: Rental Assistance (Persona 4)
- ✅ **INC-014**: Centrelink/Family Tax Benefit (Persona 2)
- ✅ **INC-015**: Medicare (Persona 3)
- ✅ **INC-016**: Jobseeker (Persona 5)
- ✅ **INC-018**: Pension (Persona 3)

### Merchants Included:
- **Known brands**: Woolworths, Coles, McDonald's, Uber, Netflix
- **Unseen/edge cases**: Sushi Hub, Brewtown Coffee, Harris Farm Markets
- **Financial institutions**: ANZ, CBA, Macquarie Bank
- **Government**: Services Australia, Centrelink
- **High-risk**: Credit Corp, Nimble, Wallet Wizard, TAB, Sportsbet

## Usage

### 1. Run Categorization System
```python
from transformer.inference.predictor_final import FinalTransactionCategorizer

predictor = FinalTransactionCategorizer(api_key='your-key')

# Process a persona
results = predictor.categorize_csv('data/test/persona1_young_professional_6month.csv')
```

### 2. Calculate Accuracy
```python
import pandas as pd

# Load results and expected
results_df = pd.read_csv('output/persona1_categorized.csv')
expected_df = pd.read_csv('data/test/persona1_young_professional_6month_expected.csv')

# Merge and compare
merged = results_df.merge(expected_df, on=['date', 'description', 'amount'])
accuracy = (merged['basiq_category'] == merged['expected_basiq']).mean()

print(f"Accuracy: {accuracy:.1%}")
```

### 3. Identify Problem Areas
```python
# Find mismatches
mismatches = merged[merged['basiq_category'] != merged['expected_basiq']]

# Group by expected category
error_by_category = mismatches.groupby('expected_basiq').size()
```

## Expected Results

### High Confidence Categories (>95% accuracy expected):
- Major grocery chains (Woolworths, Coles, Aldi)
- Major banks (ANZ, CBA, Macquarie)
- Government payments (Centrelink, Services Australia)
- BNPL providers (Afterpay, Zip, Sezzle)
- Fast food chains (McDonald's, KFC)

### Medium Confidence (80-95%):
- Unseen merchants (Sushi Hub, Brewtown Coffee)
- Generic descriptions (various small retailers)
- BS category fallback scenarios

### Critical for Credit Assessment:
- **Collection Agencies** (EXP-005): MUST be detected - indicates financial distress
- **Dishonours** (EXP-009): MUST be detected - indicates bad financial behavior
- **BNPL/SACC** (EXP-033): MUST be detected - high-risk credit indicator
- **Government Benefits** (INC-012-021): Accurate detection critical for income stability assessment

## Validation Checklist

- [ ] All 6 personas process without errors
- [ ] Collection agencies correctly identified (Persona 5)
- [ ] Dishonour fees correctly categorized as EXP-009 (Persona 5)
- [ ] BNPL correctly identified as EXP-033 (Personas 1, 4, 5)
- [ ] Youth Allowance detected as INC-012 (Persona 4)
- [ ] Medicare rebates detected as INC-015 (Persona 3)
- [ ] Jobseeker detected as INC-016 (Persona 5)
- [ ] Age Pension detected as INC-018 (Persona 3)
- [ ] Rental income detected as INC-008 (Persona 6)
- [ ] Overall accuracy >85% across all personas

## Notes

- Transactions are dated July-December 2024 (6 months)
- Amounts have ±20% variation for realistic irregularity
- Balance calculations are approximate
- All government payment amounts are based on 2024 rates
- Each persona has 95-140 transactions (realistic for 6 months)

