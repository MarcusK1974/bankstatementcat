#!/usr/bin/env python3
"""
Transaction Description Normalizer

Strips transaction type prefixes and cleans merchant names
so categorization focuses on the MERCHANT, not the payment method.
"""

import re
from typing import Tuple


class TransactionNormalizer:
    """
    Normalizes transaction descriptions by:
    1. Stripping transaction type prefixes (POS, VISA, EFTPOS, etc.)
    2. Extracting the actual merchant name
    3. Cleaning up noise (card numbers, locations, etc.)
    """
    
    # Transaction type prefixes to strip (ORDER MATTERS - longest first)
    TRANSACTION_PREFIXES = [
        # Pending transactions (check FIRST - includes other prefixes)
        r'^PENDING\s*-\s*POS\s+AUTHORISATION\s+',
        r'^PENDING\s*-\s*POS\s+PURCHASE\s+',
        r'^PENDING\s*-\s*POS\s+',
        r'^PENDING\s*-\s*VISA\s+',
        r'^PENDING\s*-\s*',
        
        # Point of Sale
        r'^POS\s+AUTHORISATION\s+',
        r'^POS\s+PURCHASE\s+',
        r'^POS\s+',
        
        # Card payments
        r'^VISA\s+DEBIT\s+PURCHASE\s+CARD\s+\d+\s+',
        r'^VISA\s+DEBIT\s+PURCHASE\s+',
        r'^VISA\s+PURCHASE\s+',
        r'^MASTERCARD\s+PURCHASE\s+',
        r'^CARD\s+PURCHASE\s+',
        
        # EFTPOS
        r'^EFTPOS\s+\d+PIN\*\s+',
        r'^EFTPOS\s+',
        
        # ATM
        r'^ATM\s+WITHDRAWAL\s+',
        r'^ATM\s+',
        
        # Direct debits
        r'^DIRECT\s+DEBIT\s+',
        r'^DD\s+',
        
        # Bank-specific online banking prefixes
        r'^ANZ\s+INTERNET\s+BANKING\s+BPAY\s+',  # ANZ BPAY payments
        r'^ANZ\s+MOBILE\s+BANKING\s+PAYMENT\s+\d+\s+TO\s+',  # ANZ mobile payments
        r'^ANZ\s+M-BANKING\s+FUNDS\s+TFER\s+TRANSFER\s+\d+\s+TO\s+',  # ANZ transfers
        r'^ANZ\s+INTERNET\s+BANKING\s+',  # Generic ANZ internet banking
        r'^ANZ\s+MOBILE\s+BANKING\s+',  # Generic ANZ mobile banking
        r'^ANZ\s+M-BANKING\s+',  # Generic ANZ mobile banking (short)
        
        # BPAY (standalone)
        r'^BPAY\s+',
        
        # Salary/Pay
        r'^PAY/SALARY\s+FROM\s+',
        r'^SALARY\s+',
        
        # Interest
        r'^CREDIT\s+INTEREST\s+PAID\s*',
        r'^DEBIT\s+INTEREST\s+',
        
        # Transfers (generic)
        r'^TRANSFER\s+FROM\s+',
        r'^TRANSFER\s+TO\s+',
        r'^TRANSFER\s+',
    ]
    
    # Location/noise patterns to remove AFTER stripping prefixes
    NOISE_PATTERNS = [
        r'\s+Card\s+Used\s+\d+',  # "Card Used 3960"
        r'\s+AU$',                 # " AU" at end
        r'\s+Card\s+\d+$',         # " Card 3960" at end
    ]
    
    def __init__(self):
        # Compile patterns for efficiency
        self.prefix_patterns = [re.compile(p, re.IGNORECASE) for p in self.TRANSACTION_PREFIXES]
        self.noise_patterns = [re.compile(p, re.IGNORECASE) for p in self.NOISE_PATTERNS]
    
    def normalize(self, description: str) -> Tuple[str, str]:
        """
        Normalize a transaction description.
        
        Args:
            description: Raw transaction description
        
        Returns:
            Tuple of (cleaned_merchant_name, transaction_type)
        """
        if not description:
            return '', 'UNKNOWN'
        
        original = description
        cleaned = description.strip()
        transaction_type = 'UNKNOWN'
        
        # Step 1: Detect and strip transaction type prefix
        for pattern in self.prefix_patterns:
            match = pattern.match(cleaned)
            if match:
                # Extract the prefix as transaction type
                prefix = match.group(0).strip()
                transaction_type = self._categorize_transaction_type(prefix)
                
                # Strip the prefix
                cleaned = pattern.sub('', cleaned).strip()
                break
        
        # Step 2: Remove noise patterns
        for pattern in self.noise_patterns:
            cleaned = pattern.sub('', cleaned).strip()
        
        # Step 3: If no merchant name left, use original
        if not cleaned or len(cleaned) < 3:
            cleaned = original
        
        return cleaned, transaction_type
    
    def _categorize_transaction_type(self, prefix: str) -> str:
        """Categorize the transaction type from prefix."""
        prefix_lower = prefix.lower()
        
        if 'pending' in prefix_lower:
            return 'PENDING'
        elif 'pos' in prefix_lower:
            return 'POS'
        elif 'visa' in prefix_lower or 'mastercard' in prefix_lower:
            return 'CARD'
        elif 'eftpos' in prefix_lower:
            return 'EFTPOS'
        elif 'atm' in prefix_lower:
            return 'ATM'
        elif 'direct debit' in prefix_lower or prefix_lower.startswith('dd'):
            return 'DIRECT_DEBIT'
        elif 'salary' in prefix_lower or 'pay/' in prefix_lower:
            return 'SALARY'
        elif 'interest' in prefix_lower:
            return 'INTEREST'
        elif 'transfer' in prefix_lower:
            return 'TRANSFER'
        else:
            return 'OTHER'
    
    def extract_merchant(self, description: str) -> str:
        """
        Extract just the merchant name, stripping all transaction metadata.
        
        This is the merchant name that should be used for categorization.
        """
        cleaned, _ = self.normalize(description)
        return cleaned


def normalize_description(description: str) -> Tuple[str, str]:
    """
    Convenience function to normalize a description.
    
    Returns:
        Tuple of (merchant_name, transaction_type)
    """
    normalizer = TransactionNormalizer()
    return normalizer.normalize(description)


if __name__ == '__main__':
    # Test cases
    test_cases = [
        "PENDING - POS AUTHORISATION BELAIR FINE WINES BELAIR AU Card Used 3960",
        "VISA DEBIT PURCHASE CARD 3960 BELAIR FINE WINES BELAIR",
        "EFTPOS 507PIN* BANKSTATEMENTS.COM.AU\\HACKNEY SA",
        "ANZ INTERNET BANKING BPAY TAX OFFICE PAYMENT {533041}",
        "ANZ MOBILE BANKING PAYMENT 168136 TO Anita ANZ Plus",
        "POS AUTHORISATION WOOLWORTHS ASHWOOD",
        "PAY/SALARY FROM VIC BUILDING AUT 2465",
        "CREDIT INTEREST PAID",
    ]
    
    normalizer = TransactionNormalizer()
    
    print("=" * 80)
    print("TRANSACTION NORMALIZATION TEST")
    print("=" * 80)
    print()
    
    for desc in test_cases:
        merchant, tx_type = normalizer.normalize(desc)
        print(f"Original:  {desc}")
        print(f"Merchant:  {merchant}")
        print(f"Type:      {tx_type}")
        print()

