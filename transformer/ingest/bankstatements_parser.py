from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class BankStatementsTransaction:
    """
    Parsed transaction from bankstatements.com.au format.
    
    Matches the structure seen in the user's example CSV.
    """
    account_type: str
    account_holder: str
    account_name: str
    bsb: str
    account_number: str
    date: str
    description: str
    amount: float
    balance: float
    category: str
    third_party: str
    transaction_type: str
    pending: bool
    
    def to_transformer_format(self) -> Dict[str, any]:
        """
        Convert to format suitable for transformer model inference.
        
        Maps bankstatements.com.au fields to BASIQ-like features.
        """
        # Parse date
        try:
            dt = datetime.fromisoformat(self.date)
            month = dt.month
            day_of_week = dt.weekday()
            day_of_month = dt.day
            year = dt.year
        except (ValueError, AttributeError):
            month = 0
            day_of_week = 0
            day_of_month = 0
            year = 0
        
        # Determine direction based on amount
        direction = "credit" if self.amount > 0 else "debit"
        
        return {
            # Text features (primary for model)
            "description": self.description,
            "merchant_name": self.third_party or "",
            "clean_description": "",  # Not available from bankstatements
            
            # Categorical features
            "bankstatements_category": self.category,  # Pre-classification
            "account_type": self.account_type,
            "transaction_type": self.transaction_type,
            "subclass_code": "",  # Not available from bankstatements
            "subclass_title": "",  # Not available from bankstatements
            "anzsic_group_code": "",  # Not available from bankstatements
            "anzsic_group_title": "",  # Not available from bankstatements
            
            # Numeric features
            "amount": self.amount,
            "direction": direction,
            
            # Temporal features
            "transaction_date": self.date,
            "month": month,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "year": year,
            
            # Metadata
            "account_holder": self.account_holder,
            "account_name": self.account_name,
            "bsb": self.bsb,
            "account_number": self.account_number,
            "balance": self.balance,
            "pending": self.pending,
        }


def parse_csv(csv_path: Path) -> List[BankStatementsTransaction]:
    """Parse bankstatements.com.au CSV format."""
    transactions = []
    
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse amount
            try:
                amount = float(row.get("amount", "0") or "0")
            except ValueError:
                amount = 0.0
            
            # Parse balance
            try:
                balance = float(row.get("Balance", "0") or "0")
            except ValueError:
                balance = 0.0
            
            # Check if pending
            pending = row.get("pending", "").lower() == "pending"
            
            tx = BankStatementsTransaction(
                account_type=row.get("accountType", ""),
                account_holder=row.get("accountHolder", ""),
                account_name=row.get("accountName", ""),
                bsb=row.get("bsb", ""),
                account_number=row.get("accountNumber", ""),
                date=row.get("date", ""),
                description=row.get("description", ""),
                amount=amount,
                balance=balance,
                category=row.get("Category", ""),
                third_party=row.get("thirdParty", ""),
                transaction_type=row.get("transactionType", ""),
                pending=pending,
            )
            transactions.append(tx)
    
    return transactions


def parse_json(json_path: Path) -> List[BankStatementsTransaction]:
    """Parse bankstatements.com.au JSON format."""
    transactions = []
    
    with json_path.open() as f:
        data = json.load(f)
    
    # Handle both array and object with transactions key
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("transactions", [])
    else:
        items = []
    
    for item in items:
        # Parse amount
        try:
            amount = float(item.get("amount", 0) or 0)
        except (ValueError, TypeError):
            amount = 0.0
        
        # Parse balance
        try:
            balance = float(item.get("balance", 0) or 0)
        except (ValueError, TypeError):
            balance = 0.0
        
        # Check if pending
        pending = item.get("pending", False)
        if isinstance(pending, str):
            pending = pending.lower() == "pending"
        
        tx = BankStatementsTransaction(
            account_type=item.get("accountType", ""),
            account_holder=item.get("accountHolder", ""),
            account_name=item.get("accountName", ""),
            bsb=item.get("bsb", ""),
            account_number=item.get("accountNumber", ""),
            date=item.get("date", ""),
            description=item.get("description", ""),
            amount=amount,
            balance=balance,
            category=item.get("category", "") or item.get("Category", ""),
            third_party=item.get("thirdParty", ""),
            transaction_type=item.get("transactionType", ""),
            pending=pending,
        )
        transactions.append(tx)
    
    return transactions


def parse_bankstatements(
    input_path: Path,
    output_path: Optional[Path] = None,
    format: str = "auto",
) -> List[BankStatementsTransaction]:
    """
    Parse bankstatements.com.au file (CSV or JSON).
    
    Args:
        input_path: Path to bankstatements file
        output_path: Optional path to write transformer-format CSV
        format: File format ('auto', 'csv', or 'json')
    
    Returns:
        List of parsed transactions
    """
    # Auto-detect format
    if format == "auto":
        if input_path.suffix.lower() == ".json":
            format = "json"
        else:
            format = "csv"
    
    # Parse file
    if format == "json":
        transactions = parse_json(input_path)
    else:
        transactions = parse_csv(input_path)
    
    print(f"Parsed {len(transactions)} transactions from {input_path}")
    
    # Write transformer format if output specified
    if output_path:
        transformer_rows = [tx.to_transformer_format() for tx in transactions]
        if transformer_rows:
            fieldnames = list(transformer_rows[0].keys())
            with output_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in transformer_rows:
                    writer.writerow(row)
            print(f"Wrote transformer-format CSV to {output_path}")
    
    return transactions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse bankstatements.com.au CSV/JSON files for ML inference."
    )
    parser.add_argument(
        "input",
        help="Path to bankstatements.com.au file (CSV or JSON)",
    )
    parser.add_argument(
        "--out",
        help="Output path for transformer-format CSV (optional)",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "csv", "json"],
        default="auto",
        help="File format (default: auto-detect)",
    )
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.out) if args.out else None
    
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    transactions = parse_bankstatements(input_path, output_path, args.format)
    
    # Show sample
    print(f"\nSample transaction:")
    if transactions:
        sample = transactions[0]
        print(f"  Description: {sample.description}")
        print(f"  Amount: ${sample.amount:.2f}")
        print(f"  Category: {sample.category}")
        print(f"  Third Party: {sample.third_party}")
        print(f"  Date: {sample.date}")


if __name__ == "__main__":
    main()

