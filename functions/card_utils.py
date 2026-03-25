# functions/card_utils.py
"""
Credit card parsing and validation utilities
"""

import re
from typing import Optional, Dict, List, Tuple

# Regular expression for card parsing
# Matches: 4111111111111111|12|25|123 or similar formats with various separators
CARD_PATTERN = re.compile(
    r'(\d{15,19})\s*[|:/\\\-\s]\s*(\d{1,2})\s*[|:/\\\-\s]\s*(\d{2,4})\s*[|:/\\\-\s]\s*(\d{3,4})'
)

# BIN ranges for major card brands (for validation)
CARD_BRANDS = {
    "VISA": r'^4[0-9]{12}(?:[0-9]{3})?$',
    "MASTERCARD": r'^5[1-5][0-9]{14}$|^2(?:2[2-9][0-9]{2}|[3-6][0-9]{3}|7[01][0-9]{2}|720[0-9])[0-9]{12}$',
    "AMEX": r'^3[47][0-9]{13}$',
    "DISCOVER": r'^6(?:011|5[0-9]{2})[0-9]{12}$',
    "JCB": r'^(?:2131|1800|35\d{3})\d{11}$',
    "DINERS": r'^3(?:0[0-5]|[68][0-9])[0-9]{11}$',
}

def parse_card(line: str) -> Optional[Dict[str, str]]:
    """
    Parse a single card line into card details
    
    Args:
        line: String containing card details (e.g., "4111111111111111|12|25|123")
    
    Returns:
        Dictionary with cc, mm, yy, cvv or None if invalid
    """
    line = line.strip()
    if not line:
        return None
    
    match = CARD_PATTERN.search(line)
    if not match:
        return None
    
    cc, mm, yy, cvv = match.groups()
    
    # Format month (always 2 digits)
    mm = mm.zfill(2)
    try:
        if int(mm) < 1 or int(mm) > 12:
            return None
    except ValueError:
        return None
    
    # Format year (always 4 digits)
    if len(yy) == 2:
        # Assume 20xx for years 00-99
        yy = "20" + yy
    if len(yy) != 4:
        return None
    
    # Basic CVV validation
    if len(cvv) not in (3, 4):
        return None
    
    return {
        "cc": cc, 
        "mm": mm, 
        "yy": yy, 
        "cvv": cvv,
        "brand": detect_card_brand(cc)
    }

def parse_cards(text: str) -> List[Dict[str, str]]:
    """
    Parse multiple cards from text (one per line)
    
    Args:
        text: Multi-line string with card details
    
    Returns:
        List of card dictionaries
    """
    cards = []
    for line_num, line in enumerate(text.strip().split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        
        card = parse_card(line)
        if card:
            cards.append(card)
    
    return cards

def format_card(card: Dict[str, str]) -> str:
    """
    Format card dictionary back to string
    
    Args:
        card: Card dictionary with cc, mm, yy, cvv
    
    Returns:
        Formatted card string (e.g., "4111111111111111|12|2025|123")
    """
    return f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"

def mask_card(card_number: str) -> str:
    """
    Mask card number for display (shows first 6 and last 4 digits)
    
    Args:
        card_number: Full card number
    
    Returns:
        Masked card number (e.g., "411111******1111")
    """
    if not card_number or len(card_number) < 6:
        return "****"
    
    first_six = card_number[:6]
    last_four = card_number[-4:]
    masked_length = len(card_number) - 10
    stars = "*" * masked_length
    
    return f"{first_six}{stars}{last_four}"

def detect_card_brand(card_number: str) -> str:
    """
    Detect card brand from card number
    
    Args:
        card_number: Card number
    
    Returns:
        Card brand name or "UNKNOWN"
    """
    for brand, pattern in CARD_BRANDS.items():
        if re.match(pattern, card_number):
            return brand
    return "UNKNOWN"

def validate_luhn(card_number: str) -> bool:
    """
    Validate card number using Luhn algorithm
    
    Args:
        card_number: Card number to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not card_number or not card_number.isdigit():
        return False
    
    total = 0
    reverse_digits = [int(d) for d in card_number[::-1]]
    
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            total += doubled if doubled < 10 else doubled - 9
        else:
            total += digit
    
    return total % 10 == 0

def validate_expiry(mm: str, yy: str) -> Tuple[bool, str]:
    """
    Validate card expiry date
    
    Args:
        mm: Month (2 digits)
        yy: Year (4 digits)
    
    Returns:
        Tuple of (is_valid, message)
    """
    from datetime import datetime
    
    try:
        mm_int = int(mm)
        yy_int = int(yy)
        
        # Basic format validation
        if not (1 <= mm_int <= 12):
            return False, "Invalid month (must be 01-12)"
        
        if len(yy) != 4 or yy_int < 2020 or yy_int > 2050:
            return False, "Invalid year"
        
        # Check if expired
        current_date = datetime.now()
        exp_date = datetime(yy_int, mm_int, 1)
        
        # Add one month to expiry date (cards expire at end of month)
        if mm_int == 12:
            exp_date = datetime(yy_int + 1, 1, 1)
        else:
            exp_date = datetime(yy_int, mm_int + 1, 1)
        
        if exp_date < datetime(current_date.year, current_date.month, 1):
            return False, "Card has expired"
        
        return True, "Valid"
        
    except ValueError as e:
        return False, f"Invalid date: {str(e)}"

def validate_cvv(cvv: str, brand: str = None) -> Tuple[bool, str]:
    """
    Validate CVV based on card brand
    
    Args:
        cvv: CVV code
        brand: Card brand (optional)
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not cvv or not cvv.isdigit():
        return False, "CVV must contain only digits"
    
    # AMEX uses 4-digit CVV, others use 3-digit
    if brand == "AMEX":
        if len(cvv) != 4:
            return False, "AMEX CVV must be 4 digits"
    else:
        if len(cvv) != 3:
            return False, "CVV must be 3 digits"
    
    return True, "Valid"

def validate_card(card: Dict[str, str], strict: bool = False) -> Tuple[bool, str]:
    """
    Complete card validation
    
    Args:
        card: Card dictionary with cc, mm, yy, cvv
        strict: If True, perform Luhn validation
    
    Returns:
        Tuple of (is_valid, message)
    """
    # Check required fields
    required_fields = ['cc', 'mm', 'yy', 'cvv']
    for field in required_fields:
        if field not in card:
            return False, f"Missing field: {field}"
    
    # Validate card number
    cc = card['cc']
    if not cc or not cc.isdigit():
        return False, "Card number must contain only digits"
    
    if len(cc) < 15 or len(cc) > 19:
        return False, f"Invalid card number length: {len(cc)} (must be 15-19 digits)"
    
    # Detect brand
    brand = detect_card_brand(cc)
    
    # Luhn validation (optional)
    if strict and not validate_luhn(cc):
        return False, "Card number failed Luhn validation"
    
    # Validate expiry
    expiry_valid, expiry_msg = validate_expiry(card['mm'], card['yy'])
    if not expiry_valid:
        return False, expiry_msg
    
    # Validate CVV
    cvv_valid, cvv_msg = validate_cvv(card['cvv'], brand)
    if not cvv_valid:
        return False, cvv_msg
    
    return True, f"Valid {brand} card"

def extract_cards_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract and validate cards from text (more aggressive parsing)
    
    Args:
        text: Raw text that may contain card details
    
    Returns:
        List of valid card dictionaries
    """
    cards = []
    
    # Try to find card-like patterns in text
    patterns = [
        # Standard format with separators
        r'(\d{15,16})[^\d]*(\d{2})[^\d]*(\d{2,4})[^\d]*(\d{3,4})',
        # Format with spaces
        r'(\d{4}\s?\d{4}\s?\d{4}\s?\d{4})\s*(\d{2})\s*/\s*(\d{2,4})\s*(\d{3,4})',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.MULTILINE)
        for match in matches:
            groups = match.groups()
            if len(groups) >= 4:
                cc = re.sub(r'\D', '', groups[0])
                mm = groups[1].strip().zfill(2)
                yy = groups[2].strip()
                cvv = groups[3].strip()
                
                # Format year
                if len(yy) == 2:
                    yy = "20" + yy
                elif len(yy) == 4:
                    pass
                else:
                    continue
                
                # Basic validation
                if len(cc) in range(15, 20) and len(cvv) in (3, 4):
                    cards.append({
                        "cc": cc,
                        "mm": mm,
                        "yy": yy,
                        "cvv": cvv,
                        "brand": detect_card_brand(cc)
                    })
    
    return cards

# Example usage
if __name__ == "__main__":
    # Test card parsing
    test_cards = [
        "4111111111111111|12|25|123",
        "5555555555554444|01|2026|456",
        "378282246310005|09|27|7890",
    ]
    
    for card_str in test_cards:
        card = parse_card(card_str)
        if card:
            print(f"Parsed: {card}")
            valid, msg = validate_card(card, strict=True)
            print(f"Validation: {msg}")
            print(f"Masked: {mask_card(card['cc'])}")
            print("-" * 50)