#!/usr/bin/env python3
"""
Internal Transfer Detector

Analyzes transaction patterns to identify transfers between user's own accounts.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple


@dataclass
class Transaction:
    """Simple transaction representation for analysis"""
    description: str
    amount: float
    date: datetime
    account_number: Optional[str] = None
    bsb: Optional[str] = None


class InternalTransferDetector:
    """
    Detects internal transfers by analyzing transaction patterns.
    
    Strategy:
    1. Extract account numbers from descriptions
    2. Find accounts that appear in both debit and credit transactions
    3. Detect matching transfer pairs (same amount, same day, opposite directions)
    4. Build a set of known user accounts
    """
    
    # Regex patterns for account detection
    ACCOUNT_PATTERNS = [
        # BSB-Account format: 012-345, 012345
        r'\b(\d{3})[- ]?(\d{6,9})\b',
        # Account number in transfers: "TO 012345678", "FROM 012345678"
        r'(?:TO|FROM)\s+(\d{6,9})\b',
        # Transfer references
        r'TRANSFER\s+\d+\s+(?:TO|FROM)\s+(\d{6,9})',
    ]
    
    # Keywords indicating transfers
    TRANSFER_KEYWORDS = [
        'TFER', 'TRANSFER', 'FUNDS TFER', 'M-BANKING FUNDS',
        'INTERNET BANKING PAYMENT', 'MOBILE BANKING PAYMENT',
    ]
    
    # Keywords indicating internal transfers from BS categorization
    INTERNAL_INDICATORS = [
        'Internal Transfer', 'Internal Transfer Credit', 'Internal Transfer Debit'
    ]
    
    def __init__(self):
        self.user_accounts: Set[str] = set()
        self.transaction_accounts: Dict[str, List[float]] = defaultdict(list)  # account -> amounts
        self._initialized = False
    
    def analyze_transactions(self, transactions: List[Dict]) -> None:
        """
        Analyze a batch of transactions to identify user's accounts.
        
        Args:
            transactions: List of transaction dicts with keys:
                - description
                - amount
                - date (datetime or ISO string)
                - account_number (optional)
                - bsb (optional)
                - bs_category (optional)
        """
        parsed_txs = []
        
        for tx in transactions:
            # Parse date
            date = tx.get('date')
            if isinstance(date, str):
                try:
                    date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                except:
                    try:
                        date = datetime.strptime(date, '%Y-%m-%d')
                    except:
                        continue
            
            parsed_tx = Transaction(
                description=tx.get('description', ''),
                amount=float(tx.get('amount', 0)),
                date=date,
                account_number=tx.get('account_number'),
                bsb=tx.get('bsb')
            )
            parsed_txs.append(parsed_tx)
            
            # Add user's own account if provided
            if parsed_tx.account_number:
                account_key = f"{parsed_tx.bsb or ''}{parsed_tx.account_number}"
                self.user_accounts.add(account_key)
        
        # Strategy 1: Extract accounts from descriptions
        extracted_accounts = self._extract_accounts_from_descriptions(parsed_txs)
        
        # Strategy 2: Find accounts appearing in both credits and debits
        bidirectional_accounts = self._find_bidirectional_accounts(parsed_txs, extracted_accounts)
        
        # Strategy 3: Find matching transfer pairs
        transfer_pairs = self._find_transfer_pairs(parsed_txs, extracted_accounts)
        
        # Strategy 4: Check BS category hints
        bs_internal_accounts = self._extract_from_bs_categories(transactions, extracted_accounts)
        
        # Combine results
        self.user_accounts.update(bidirectional_accounts)
        self.user_accounts.update(transfer_pairs)
        self.user_accounts.update(bs_internal_accounts)
        
        self._initialized = True
    
    def _extract_accounts_from_descriptions(self, transactions: List[Transaction]) -> Dict[str, List[Tuple[float, str]]]:
        """Extract account numbers from transaction descriptions."""
        accounts = defaultdict(list)
        
        for tx in transactions:
            desc = tx.description
            
            # Try each pattern
            for pattern in self.ACCOUNT_PATTERNS:
                matches = re.finditer(pattern, desc, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) == 2:
                        # BSB + account
                        account = f"{match.group(1)}{match.group(2)}"
                    else:
                        # Just account
                        account = match.group(1)
                    
                    # Store with amount and direction
                    direction = 'credit' if tx.amount > 0 else 'debit'
                    accounts[account].append((tx.amount, direction))
        
        return accounts
    
    def _find_bidirectional_accounts(
        self, 
        transactions: List[Transaction],
        extracted_accounts: Dict[str, List[Tuple[float, str]]]
    ) -> Set[str]:
        """Find accounts that appear in both credit and debit transactions."""
        bidirectional = set()
        
        for account, amounts_dirs in extracted_accounts.items():
            directions = set(direction for _, direction in amounts_dirs)
            
            # If account appears in both credits and debits, it's likely internal
            if 'credit' in directions and 'debit' in directions:
                bidirectional.add(account)
        
        return bidirectional
    
    def _find_transfer_pairs(
        self,
        transactions: List[Transaction],
        extracted_accounts: Dict[str, List[Tuple[float, str]]]
    ) -> Set[str]:
        """Find matching transfer pairs (same amount, same day, opposite directions)."""
        transfer_accounts = set()
        
        # Group by date
        by_date = defaultdict(list)
        for tx in transactions:
            date_key = tx.date.date()
            by_date[date_key].append(tx)
        
        # Find matching pairs
        for date_key, day_txs in by_date.items():
            for i, tx1 in enumerate(day_txs):
                if not self._is_transfer_description(tx1.description):
                    continue
                
                for tx2 in day_txs[i+1:]:
                    if not self._is_transfer_description(tx2.description):
                        continue
                    
                    # Check if amounts match (opposite signs)
                    if abs(abs(tx1.amount) - abs(tx2.amount)) < 0.01:
                        if (tx1.amount > 0 and tx2.amount < 0) or (tx1.amount < 0 and tx2.amount > 0):
                            # Extract accounts from both
                            accounts1 = self._extract_accounts_from_single_description(tx1.description)
                            accounts2 = self._extract_accounts_from_single_description(tx2.description)
                            
                            transfer_accounts.update(accounts1)
                            transfer_accounts.update(accounts2)
        
        return transfer_accounts
    
    def _extract_from_bs_categories(
        self,
        transactions: List[Dict],
        extracted_accounts: Dict[str, List[Tuple[float, str]]]
    ) -> Set[str]:
        """Extract accounts from transactions marked as 'Internal Transfer' by BS."""
        internal_accounts = set()
        
        for tx in transactions:
            bs_cat = tx.get('bs_category', '')
            third_party = tx.get('third_party', '')
            
            # Check if BS marked it as internal
            if any(indicator in bs_cat for indicator in self.INTERNAL_INDICATORS) or \
               any(indicator in third_party for indicator in self.INTERNAL_INDICATORS):
                # Extract account from description
                desc = tx.get('description', '')
                accounts = self._extract_accounts_from_single_description(desc)
                internal_accounts.update(accounts)
        
        return internal_accounts
    
    def _extract_accounts_from_single_description(self, description: str) -> Set[str]:
        """Extract all account numbers from a single description."""
        accounts = set()
        
        for pattern in self.ACCOUNT_PATTERNS:
            matches = re.finditer(pattern, description, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    account = f"{match.group(1)}{match.group(2)}"
                else:
                    account = match.group(1)
                accounts.add(account)
        
        return accounts
    
    def _is_transfer_description(self, description: str) -> bool:
        """Check if description indicates a transfer."""
        desc_upper = description.upper()
        return any(keyword in desc_upper for keyword in self.TRANSFER_KEYWORDS)
    
    def is_internal_transfer(
        self,
        description: str,
        amount: float,
        bs_category: Optional[str] = None,
        third_party: Optional[str] = None
    ) -> bool:
        """
        Determine if a transaction is an internal transfer.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            bs_category: Optional BS category
            third_party: Optional BS third party field
        
        Returns:
            True if internal transfer, False otherwise
        """
        if not self._initialized:
            # No analysis done yet, use simple heuristics
            return self._simple_internal_check(description, bs_category, third_party)
        
        # Check BS category hint
        if bs_category and any(indicator in bs_category for indicator in self.INTERNAL_INDICATORS):
            return True
        
        if third_party and any(indicator in third_party for indicator in self.INTERNAL_INDICATORS):
            return True
        
        # Check if transfer keyword present
        if not self._is_transfer_description(description):
            return False
        
        # Extract accounts from description
        accounts = self._extract_accounts_from_single_description(description)
        
        # Check if any extracted account is in our user accounts
        for account in accounts:
            if account in self.user_accounts:
                return True
            
            # Also check partial matches (last 6-9 digits)
            for user_account in self.user_accounts:
                if account in user_account or user_account in account:
                    if len(account) >= 6:  # Reasonable account number length
                        return True
        
        return False
    
    def _simple_internal_check(
        self,
        description: str,
        bs_category: Optional[str],
        third_party: Optional[str]
    ) -> bool:
        """Simple heuristic check when no analysis has been done."""
        # Check BS hints
        if bs_category and any(indicator in bs_category for indicator in self.INTERNAL_INDICATORS):
            return True
        
        if third_party and any(indicator in third_party for indicator in self.INTERNAL_INDICATORS):
            return True
        
        # Conservative: don't classify as internal without more info
        return False
    
    def get_user_accounts(self) -> Set[str]:
        """Get the set of detected user accounts."""
        return self.user_accounts.copy()


def create_detector(transactions: List[Dict]) -> InternalTransferDetector:
    """
    Factory function to create and initialize a detector.
    
    Args:
        transactions: List of transactions for analysis
    
    Returns:
        Initialized InternalTransferDetector
    """
    detector = InternalTransferDetector()
    detector.analyze_transactions(transactions)
    return detector

