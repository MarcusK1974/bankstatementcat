#!/usr/bin/env python3
"""
Income Transaction Prioritizer

For POSITIVE transactions, prioritizes income-type keywords over merchant names.
This prevents "WOOLWORTHS WAGES" from being categorized as Groceries instead of Salary.

Priority Order for Positive Transactions:
1. Income-type keywords (wages, salary, pay from) → INC-009 (Salary)
2. Specific benefit keywords (youth allowance, centrelink) → INC-012, INC-014, etc.
3. Refund keywords (refund, return, reversal) → EXP-032 (Returns & Refunds)
4. Other income sources (dividends, rental income, etc.)
"""

import re
from typing import Optional, Tuple

# Priority 1: Employment Income Keywords (INC-009: Salary)
SALARY_KEYWORDS = [
    'wage', 'wages', 'salary', 'salaries',
    'pay from', 'payment from', 'payroll',
    'fortnightly pay', 'weekly pay', 'monthly pay',
    'net pay', 'gross pay',
    'employer payment', 'employment income'
]

# Priority 2: Government Benefits (Various INC codes)
BENEFIT_KEYWORDS = {
    'INC-012': [  # Youth Allowance
        'youth allowance', 'austudy', 'abstudy'
    ],
    'INC-014': [  # Centrelink
        'centrelink', 'services australia',
        'family tax benefit', 'ftb',
        'parenting payment', 'carer payment'
    ],
    'INC-016': [  # Jobseeker
        'jobseeker', 'newstart', 'job seeker'
    ],
    'INC-017': [  # Age Pension
        'age pension', 'aged pension'
    ],
    'INC-018': [  # Disability Support Pension
        'disability support', 'dsp', 'disability pension'
    ],
}

# Priority 3: Refund Keywords (EXP-032: Returns & Refunds)
REFUND_KEYWORDS = [
    'refund', 'return', 'reversal', 'reversed',
    'credit adjustment', 'chargeback',
    'reimbursement', 'rebate'
]

# Priority 4: Other Income Sources
OTHER_INCOME_KEYWORDS = {
    'INC-001': [  # Business Income
        'invoice payment', 'client payment', 'payment received',
        'stripe transfer', 'paypal transfer',
        'square deposit', 'eftpos settlement'
    ],
    'INC-002': [  # Child Support Income
        'child support', 'child maintenance'
    ],
    'INC-005': [  # Dividend Income
        'dividend', 'div payment', 'stock dividend',
        'share dividend', 'distribution'
    ],
    'INC-008': [  # Rental Income
        'rental income', 'rent received', 'property income'
    ],
    'INC-010': [  # Superannuation Income
        'super payment', 'superannuation payment',
        'pension payment', 'annuity'
    ],
    'INC-013': [  # Investment Income
        'interest credit', 'interest received',
        'investment return', 'bond payment'
    ],
    'INC-015': [  # Medicare
        'medicare benefit', 'mcare benefit',
        'health insurance rebate'
    ],
    'INC-019': [  # Lump Sum
        'inheritance', 'estate payment',
        'insurance payout', 'settlement'
    ],
    'INC-020': [  # Commission Income
        'commission payment', 'sales commission',
        'referral fee', 'affiliate payment'
    ],
    'INC-021': [  # Bonus Income
        'bonus payment', 'performance bonus',
        'annual bonus', 'incentive payment'
    ],
}


def check_income_priority(description: str) -> Optional[Tuple[str, float, str]]:
    """
    Check if a POSITIVE transaction matches income-type keywords.
    
    This should be called BEFORE checking merchant names in the comprehensive database.
    
    Args:
        description: Normalized transaction description (lowercase)
        
    Returns:
        Tuple of (category_code, confidence, reason) or None if no match
    """
    desc_lower = description.lower()
    
    # Priority 1: Salary/Wages (INC-009)
    for keyword in SALARY_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, desc_lower):
            return 'INC-009', 0.99, f'Salary keyword: {keyword}'
    
    # Priority 2: Government Benefits
    for category, keywords in BENEFIT_KEYWORDS.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, desc_lower):
                return category, 0.99, f'Benefit keyword: {keyword}'
    
    # Priority 3: Refunds (EXP-032)
    for keyword in REFUND_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, desc_lower):
            return 'EXP-032', 0.98, f'Refund keyword: {keyword}'
    
    # Priority 4: Other Income Sources
    for category, keywords in OTHER_INCOME_KEYWORDS.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, desc_lower):
                return category, 0.98, f'Income keyword: {keyword}'
    
    # No income keyword match - proceed to comprehensive database
    return None


def filter_category_by_direction(category_code: str, amount: float) -> bool:
    """
    Check if a category code is valid for the transaction direction.
    
    Args:
        category_code: BASIQ category code (e.g., 'EXP-016', 'INC-009')
        amount: Transaction amount (negative = expense, positive = income)
        
    Returns:
        True if category is valid for this direction, False otherwise
    """
    if amount < 0:
        # Negative = Expense (must be EXP-*)
        return category_code.startswith('EXP-')
    elif amount > 0:
        # Positive = Income (must be INC-* OR EXP-032 for refunds)
        return category_code.startswith('INC-') or category_code == 'EXP-032'
    else:
        # Zero amount - allow both
        return True

