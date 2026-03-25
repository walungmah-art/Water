# functions/bin_utils.py
"""
BIN (Bank Identification Number) utilities for generating valid test cards
Handles both short BINs (6 digits) and longer partial card numbers
"""

import random
import re
import datetime
from typing import List, Dict, Optional, Tuple

def luhn_checksum(card_number: str) -> int:
    """
    Calculate Luhn checksum digit for a partial card number
    
    Args:
        card_number: Partial card number (without checksum)
    
    Returns:
        Checksum digit
    """
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(digits_of(d * 2))
    return (total * 9) % 10

def generate_luhn_card(prefix: str, length: int = 16) -> str:
    """
    Generate a valid card number using Luhn algorithm
    
    Args:
        prefix: Card prefix (BIN or partial card number)
        length: Total card length (default 16)
    
    Returns:
        Valid card number
    """
    # Remove any non-digit characters
    prefix = re.sub(r'\D', '', prefix)
    
    # If prefix is already longer than target length, truncate
    if len(prefix) >= length:
        prefix = prefix[:length-1]
    
    # Calculate how many digits we need to generate
    remaining_length = length - len(prefix) - 1  # -1 for checksum
    
    if remaining_length < 0:
        raise ValueError(f"Prefix too long for card length {length}")
    
    # Generate random digits for the middle part
    middle = ''.join(str(random.randint(0, 9)) for _ in range(remaining_length))
    
    # Combine prefix + middle (without checksum)
    partial = prefix + middle
    
    # Calculate checksum
    checksum = luhn_checksum(partial)
    
    # Return complete card number
    return partial + str(checksum)

def validate_luhn_full(card_number: str) -> bool:
    """
    Validate a complete card number using Luhn algorithm
    
    Args:
        card_number: Full card number
    
    Returns:
        True if valid, False otherwise
    """
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(digits_of(d * 2))
    return total % 10 == 0

def detect_card_brand(bin_prefix: str) -> Tuple[str, int, int, List[int]]:
    """
    Detect card brand from BIN prefix with valid lengths
    
    Args:
        bin_prefix: First few digits of card (at least 6)
    
    Returns:
        Tuple of (brand, default_length, cvv_length, valid_lengths)
    """
    # Remove non-digits and take first 6 for detection
    clean = re.sub(r'\D', '', bin_prefix)
    first_6 = clean[:6] if len(clean) >= 6 else clean.ljust(6, '0')
    
    # AMEX: 34, 37 - 15 digits
    if first_6.startswith(('34', '37')):
        return ("AMEX", 15, 4, [15])
    
    # Visa: 4 - 13, 16, or 19 digits
    elif first_6.startswith('4'):
        return ("VISA", 16, 3, [13, 16, 19])
    
    # Mastercard: 51-55, 2221-2720 - 16 digits
    elif (51 <= int(first_6[:2]) <= 55) or (2221 <= int(first_6[:4]) <= 2720):
        return ("MASTERCARD", 16, 3, [16])
    
    # Discover: 6011, 65, 644-649, 622126-622925 - 16 digits
    elif (first_6.startswith(('6011', '65')) or 
          (644 <= int(first_6[:3]) <= 649) or
          (622126 <= int(first_6[:6]) <= 622925)):
        return ("DISCOVER", 16, 3, [16, 19])
    
    # JCB: 35 - 16 digits
    elif first_6.startswith('35'):
        return ("JCB", 16, 3, [16])
    
    # Diners Club: 300-305, 36, 38-39 - 14 digits
    elif (300 <= int(first_6[:3]) <= 305) or first_6.startswith(('36', '38', '39')):
        return ("DINERS", 14, 3, [14])
    
    # Default to VISA
    else:
        return ("UNKNOWN", 16, 3, [16])

def determine_target_length(input_length: int, valid_lengths: List[int]) -> int:
    """
    Determine the target card length based on input length
    
    Args:
        input_length: Length of user input
        valid_lengths: List of valid lengths for this card brand
    
    Returns:
        Target card length
    """
    # Find the smallest valid length that's >= input_length
    for length in sorted(valid_lengths):
        if length >= input_length:
            return length
    
    # If no valid length found, use the largest valid length
    return max(valid_lengths)

def generate_expiry_date(future_years: int = 3) -> Tuple[str, str]:
    """
    Generate a future expiry date
    
    Args:
        future_years: How many years in future to generate
    
    Returns:
        Tuple of (month, year) as strings (4-digit year)
    """
    now = datetime.datetime.now()
    
    # Random month (1-12)
    month = random.randint(1, 12)
    
    # Random year (current year + 1 to current year + future_years)
    year = now.year + random.randint(1, future_years)
    
    # Format month as 2 digits
    month_str = f"{month:02d}"
    
    # Return 4-digit year
    return (month_str, str(year))

def generate_cvv(brand: str) -> str:
    """
    Generate CVV based on card brand
    
    Args:
        brand: Card brand (AMEX, VISA, etc.)
    
    Returns:
        CVV as string
    """
    if brand == "AMEX":
        # AMEX uses 4-digit CVV
        return ''.join(str(random.randint(0, 9)) for _ in range(4))
    else:
        # Most cards use 3-digit CVV
        return ''.join(str(random.randint(0, 9)) for _ in range(3))

def generate_next_card(user_input: str, max_attempts: int = 10) -> Optional[Dict[str, str]]:
    """
    Generate a single valid card from user input (BIN or partial card number)
    
    Args:
        user_input: User input (can be 6+ digits, partial card number)
        max_attempts: Maximum attempts to generate a valid card
    
    Returns:
        Card dictionary or None if failed
    """
    # Clean the input
    input_clean = re.sub(r'\D', '', user_input)
    
    if len(input_clean) < 6:
        return None
    
    # Detect card brand from first 6 digits
    brand, default_length, cvv_length, valid_lengths = detect_card_brand(input_clean)
    
    # Determine target card length based on input length
    input_length = len(input_clean)
    target_length = determine_target_length(input_length, valid_lengths)
    
    # If input is longer than target, truncate to leave room for checksum
    if input_length >= target_length:
        input_clean = input_clean[:target_length - 1]
        input_length = len(input_clean)
    
    for attempt in range(max_attempts):
        try:
            if input_length < target_length:
                # Need to generate more digits
                remaining = target_length - input_length - 1  # -1 for checksum
                
                if remaining > 0:
                    # Generate middle digits
                    middle = ''.join(str(random.randint(0, 9)) for _ in range(remaining))
                    partial = input_clean + middle
                else:
                    partial = input_clean
                
                # Calculate checksum
                checksum = luhn_checksum(partial)
                card_number = partial + str(checksum)
            else:
                # Input is exactly at target length, just ensure checksum is correct
                # This shouldn't happen often, but handle it
                partial = input_clean[:-1]
                checksum = luhn_checksum(partial)
                card_number = partial + str(checksum)
            
            # Double-check Luhn validation
            if not validate_luhn_full(card_number):
                continue
            
            # Verify length is valid
            if len(card_number) not in valid_lengths:
                continue
            
            # Generate expiry date
            month, year_4digit = generate_expiry_date(future_years=3)
            
            # Generate CVV
            cvv = generate_cvv(brand)
            
            # Create card in 4-digit year format
            card_str = f"{card_number}|{month}|{year_4digit}|{cvv}"
            
            # Calculate how many digits were generated
            generated_digits = len(card_number) - input_length
            
            return {
                "cc": card_number,
                "month": month,
                "year": year_4digit,
                "cvv": cvv,
                "brand": brand,
                "card_string": card_str,
                "length": len(card_number),
                "input_length": input_length,
                "generated_digits": generated_digits,
                "input_used": input_clean
            }
            
        except Exception:
            continue
    
    # If all attempts fail, try one last time with default approach
    try:
        # Use the first 6 digits as BIN and generate full card
        bin_6 = input_clean[:6]
        card_number = generate_luhn_card(bin_6, default_length)
        
        if validate_luhn_full(card_number):
            month, year_4digit = generate_expiry_date(future_years=3)
            cvv = generate_cvv(brand)
            card_str = f"{card_number}|{month}|{year_4digit}|{cvv}"
            
            return {
                "cc": card_number,
                "month": month,
                "year": year_4digit,
                "cvv": cvv,
                "brand": brand,
                "card_string": card_str,
                "length": len(card_number),
                "input_length": 6,
                "generated_digits": len(card_number) - 6,
                "input_used": bin_6
            }
    except:
        pass
    
    return None

def format_card_for_display(card: Dict[str, str], show_brand: bool = True, show_details: bool = False) -> str:
    """
    Format a single card for display
    
    Args:
        card: Card dictionary
        show_brand: Whether to show card brand
        show_details: Whether to show generation details
    
    Returns:
        Formatted string
    """
    brand_info = f" [{card['brand']}]" if show_brand else ""
    card_line = f"<code>{card['card_string']}</code>{brand_info}"
    
    if show_details and 'generated_digits' in card:
        details = f" (Used {card['input_length']} digits, generated {card['generated_digits']})"
        return card_line + details
    
    return card_line

def batch_generate_cards(user_input: str, count: int = 5) -> List[Dict[str, str]]:
    """
    Generate multiple valid cards from user input
    
    Args:
        user_input: User input (BIN or partial card number)
        count: Number of cards to generate
    
    Returns:
        List of card dictionaries
    """
    cards = []
    attempts = 0
    max_attempts = count * 10  # Allow more attempts to get valid cards
    
    # Get card info for display
    brand, default_length, _, valid_lengths = detect_card_brand(user_input)
    input_length = len(re.sub(r'\D', '', user_input))
    target_length = determine_target_length(input_length, valid_lengths)
    
    while len(cards) < count and attempts < max_attempts:
        card = generate_next_card(user_input)
        if card:
            # Avoid duplicates
            if not any(c['cc'] == card['cc'] for c in cards):
                cards.append(card)
        attempts += 1
    
    return cards

def get_card_info(user_input: str) -> Dict:
    """
    Get information about what will be generated from user input
    
    Args:
        user_input: User input (BIN or partial card number)
    
    Returns:
        Dictionary with generation info
    """
    input_clean = re.sub(r'\D', '', user_input)
    brand, default_length, cvv_length, valid_lengths = detect_card_brand(input_clean)
    input_length = len(input_clean)
    target_length = determine_target_length(input_length, valid_lengths)
    
    if input_length >= target_length:
        action = f"Will use as complete card (truncate to {target_length-1} digits + checksum)"
        will_generate = 1  # Just checksum
    else:
        will_generate = target_length - input_length
        action = f"Will generate {will_generate} digits"
    
    return {
        "input": input_clean,
        "input_length": input_length,
        "brand": brand,
        "cvv_length": cvv_length,
        "valid_lengths": valid_lengths,
        "target_length": target_length,
        "will_generate": will_generate,
        "action": action
    }

# Example usage and testing
if __name__ == "__main__":
    # Test different inputs
    test_inputs = [
        "374355",           # 6-digit BIN
        "3743551236",       # 10-digit partial
        "37435512345678",   # 14-digit partial
        "411111",           # Visa BIN
        "555555",           # Mastercard BIN
    ]
    
    for test_input in test_inputs:
        print(f"\n{'='*50}")
        print(f"Input: {test_input}")
        info = get_card_info(test_input)
        print(f"Brand: {info['brand']}")
        print(f"Target length: {info['target_length']} digits")
        print(f"Action: {info['action']}")
        
        # Generate 2 sample cards
        cards = batch_generate_cards(test_input, 2)
        for i, card in enumerate(cards, 1):
            print(f"Card {i}: {format_card_for_display(card, show_details=True)}")