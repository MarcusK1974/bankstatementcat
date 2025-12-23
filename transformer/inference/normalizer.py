#!/usr/bin/env python3
"""
Transaction Description Normalization

Normalizes transaction descriptions for consistent pattern matching and learning.
Aggressive normalization to ensure "KFC MELBOURNE" and "KFC SYDNEY" map to the same pattern.
"""

import re
from typing import Set


# Australian states and territories
AUSTRALIAN_LOCATIONS = {
    'nsw', 'vic', 'qld', 'wa', 'sa', 'tas', 'act', 'nt',
    'new south wales', 'victoria', 'queensland', 'western australia',
    'south australia', 'tasmania', 'australian capital territory',
    'northern territory',
    # Major cities
    'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide', 'hobart',
    'darwin', 'canberra', 'gold coast', 'newcastle', 'wollongong',
    'geelong', 'townsville', 'cairns', 'toowoomba', 'ballarat',
    'bendigo', 'albury', 'launceston', 'mackay', 'rockhampton',
    'parramatta', 'blacktown', 'penrith', 'bondi', 'manly',
}

# Common transaction prefixes to remove
TRANSACTION_PREFIXES = [
    'payment to', 'transfer to', 'transfer from',
    'eftpos', 'visa debit purchase card', 'visa purchase',
    'direct debit', 'direct credit', 'card purchase',
    'atm withdrawal', 'bpay', 'paypal', 'recurring payment',
    'pending -', 'pending', 'pay/salary from',
    'anz mobile banking payment', 'anz internet banking payment',
    'anz m-banking funds tfer transfer', 'internet banking',
    'mobile banking', 'm-banking', 'funds tfer transfer',
]

# Common suffixes to remove
TRANSACTION_SUFFIXES = [
    'au', 'pty ltd', 'ltd', 'pty', 'australia',
]


def normalize_description(description: str) -> str:
    """
    Normalize transaction description to a canonical form.
    
    This is the main entry point for normalization.
    
    Args:
        description: Raw transaction description
    
    Returns:
        Normalized description (lowercase, cleaned)
    
    Examples:
        >>> normalize_description("WOOLWORTHS 1234 MELBOURNE VIC")
        'woolworths'
        >>> normalize_description("KFC PARRAMATTA NSW")
        'kfc'
        >>> normalize_description("PAYMENT TO MOMENTUM ENERGY 23522784")
        'momentum energy'
    """
    if not description:
        return ""
    
    # Convert to lowercase
    text = description.lower().strip()
    
    # Remove transaction prefixes
    text = _remove_prefixes(text)
    
    # Remove reference numbers (sequences of 4+ digits)
    text = _remove_reference_numbers(text)
    
    # Remove locations
    text = _remove_locations(text)
    
    # Remove special characters except spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    # Remove transaction suffixes
    text = _remove_suffixes(text)
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Extract merchant name (most important part)
    text = extract_merchant_name(text)
    
    return text


def extract_merchant_name(text: str) -> str:
    """
    Extract the core merchant/entity name from normalized text.
    
    Takes already-normalized text and extracts the key merchant identifier.
    
    Args:
        text: Normalized text (lowercase, cleaned)
    
    Returns:
        Core merchant name
    
    Examples:
        >>> extract_merchant_name("woolworths store")
        'woolworths'
        >>> extract_merchant_name("uber eats order")
        'uber eats'
    """
    if not text:
        return ""
    
    # Common word patterns that indicate merchant name
    # Keep first 1-3 words depending on common patterns
    words = text.split()
    
    if not words:
        return ""
    
    # Single word merchant - keep it
    if len(words) == 1:
        return words[0]
    
    # Two-word merchants (common for brands)
    # e.g., "momentum energy", "origin energy", "red energy"
    if len(words) == 2:
        return ' '.join(words)
    
    # Three+ words - need to be smart about what to keep
    # Check if first two words form a known brand pattern
    first_two = ' '.join(words[:2])
    
    # Common multi-word brands/entities
    multi_word_patterns = [
        'momentum energy', 'origin energy', 'agl energy', 'red energy',
        'uber eats', 'menu log', 'uber taxi',
        'tax office', 'services australia', 'medicare australia',
        'woolworths', 'coles', 'aldi', 'iga',
    ]
    
    for pattern in multi_word_patterns:
        if first_two == pattern or text.startswith(pattern):
            return pattern
    
    # Default: keep first 2 words (usually the brand)
    return ' '.join(words[:2])


def _remove_prefixes(text: str) -> str:
    """Remove common transaction prefixes."""
    for prefix in TRANSACTION_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            # Check again in case there are multiple prefixes
            return _remove_prefixes(text)
    return text


def _remove_suffixes(text: str) -> str:
    """Remove common transaction suffixes."""
    for suffix in TRANSACTION_SUFFIXES:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
            # Check again in case there are multiple suffixes
            return _remove_suffixes(text)
    return text


def _remove_reference_numbers(text: str) -> str:
    """
    Remove reference numbers and long digit sequences.
    
    Keeps card numbers (4 digits) but removes longer sequences.
    """
    # Remove sequences of 5+ digits
    text = re.sub(r'\b\d{5,}\b', '', text)
    
    # Remove common reference patterns
    text = re.sub(r'\{\d+\}', '', text)  # {123456}
    text = re.sub(r'ref\s*\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'reference\s*\d+', '', text, flags=re.IGNORECASE)
    
    return text


def _remove_locations(text: str) -> str:
    """Remove Australian location identifiers."""
    words = text.split()
    filtered_words = []
    
    for word in words:
        # Remove if it's a known location
        if word not in AUSTRALIAN_LOCATIONS:
            filtered_words.append(word)
    
    return ' '.join(filtered_words)


def remove_location_identifiers(text: str) -> str:
    """
    Public function to remove location identifiers from text.
    
    Useful for testing or when you want just this specific normalization.
    """
    return _remove_locations(text.lower())


def normalize_for_lookup(description: str) -> str:
    """
    Normalize for dictionary lookup.
    
    Alias for normalize_description, but makes intent clearer.
    """
    return normalize_description(description)


def get_normalization_variants(description: str) -> Set[str]:
    """
    Get multiple normalization variants for fuzzy matching.
    
    Returns a set of possible normalized forms to check against learned patterns.
    Useful for improving match rate.
    
    Args:
        description: Raw transaction description
    
    Returns:
        Set of normalized variants
    """
    variants = set()
    
    # Full normalization
    full_norm = normalize_description(description)
    variants.add(full_norm)
    
    # Just first word
    if full_norm:
        first_word = full_norm.split()[0]
        if len(first_word) >= 3:  # Ignore very short words
            variants.add(first_word)
    
    # First two words
    words = full_norm.split()
    if len(words) >= 2:
        variants.add(' '.join(words[:2]))
    
    return variants


# Convenience function for testing
def test_normalization():
    """Test normalization with common examples."""
    test_cases = [
        "WOOLWORTHS 1234 MELBOURNE VIC",
        "KFC PARRAMATTA NSW",
        "PAYMENT TO MOMENTUM ENERGY 23522784",
        "EFTPOS YELLOW CAB SA 132227 GLANDORE AU",
        "ANZ INTERNET BANKING BPAY TAX OFFICE PAYMENT {533041}",
        "VISA DEBIT PURCHASE CARD 3960 OTR BLACKWOOD BLACKW",
        "PAY/SALARY FROM VIC BUILDING AUT 2465",
        "TRANSFER FROM MCARE BENEFITS 198145800 CYWQ",
    ]
    
    print("Normalization Test Results:")
    print("=" * 70)
    for desc in test_cases:
        normalized = normalize_description(desc)
        print(f"Original:    {desc}")
        print(f"Normalized:  {normalized}")
        print()


if __name__ == '__main__':
    test_normalization()

