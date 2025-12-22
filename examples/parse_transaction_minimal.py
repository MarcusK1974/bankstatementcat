from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List


def _safe_decimal(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _redact(text: str) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= 6:
        return "[REDACTED]"
    return f"{cleaned[:3]}...{cleaned[-3:]}"


def parse_transaction(tx: Dict[str, Any]) -> Dict[str, str]:
    return {
        "transaction_id": str(tx.get("id") or ""),
        "amount": _safe_decimal(tx.get("amount")),
        "direction": str(tx.get("direction") or ""),
        "transaction_date": str(tx.get("transactionDate") or ""),
        "post_date": str(tx.get("postDate") or ""),
        "description": str(tx.get("description") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a retrieve-transactions JSON into canonical rows."
    )
    parser.add_argument("path", help="Path to retrieve-transactions_*.json")
    args = parser.parse_args()

    path = Path(args.path)
    data = json.loads(path.read_text())
    items = data.get("data") if isinstance(data, dict) else []
    rows: List[Dict[str, str]] = [parse_transaction(tx) for tx in (items or [])]

    print(f"Parsed {len(rows)} transactions from {path.name}")
    for row in rows[:3]:
        safe = row.copy()
        safe["description"] = _redact(safe["description"])
        print(safe)


if __name__ == "__main__":
    main()
