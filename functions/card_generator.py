# functions/card_generator.py
"""
Card generator using Luhn algorithm with live BIN info from antipublic API
Preserves original UI formatting
"""

import requests
import re
import random
from datetime import datetime
from typing import Optional, Dict, Tuple, List

class CardGenerator:
    def __init__(self):
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
    
    def luhn_checksum(self, card_number):
        """Calculate Luhn checksum"""
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10
    
    def calculate_luhn(self, partial_card_number):
        """Calculate the last digit (checksum) using Luhn algorithm"""
        partial = str(partial_card_number)
        # Add a placeholder for the check digit
        test_number = partial + '0'
        checksum = self.luhn_checksum(test_number)
        check_digit = (10 - checksum) % 10
        return partial + str(check_digit)
    
    def is_amex(self, bin_num):
        """Check if BIN belongs to American Express"""
        bin_prefix = bin_num[:2] if len(bin_num) >= 2 else bin_num
        return bin_prefix in ['34', '37']
    
    def generate_card_number(self, pattern):
        """Generate a valid card number using Luhn algorithm"""
        # Remove any non-digit characters
        pattern = str(pattern)
        pattern = re.sub(r'[^0-9xX]', '', pattern)
        
        # Check if it's AmEx
        is_amex = self.is_amex(pattern)
        
        # AmEx uses 15 digits total (14 + checksum)
        # Others use 16 digits total (15 + checksum)
        target_length = 14 if is_amex else 15
        
        # If pattern has X's, replace them with random digits
        if 'x' in pattern.lower():
            card_digits = []
            for char in pattern:
                if char.lower() == 'x':
                    card_digits.append(str(random.randint(0, 9)))
                else:
                    card_digits.append(char)
            partial = ''.join(card_digits)
        else:
            # Generate remaining digits
            remaining = target_length - len(pattern)
            
            if remaining > 0:
                # Generate random digits for missing positions
                partial = pattern + ''.join([str(random.randint(0, 9)) for _ in range(remaining)])
            elif remaining < 0:
                # Pattern is longer than target, truncate to first target_length digits
                partial = pattern[:target_length]
            else:
                # Pattern is exactly target length
                partial = pattern
        
        # Ensure we have exactly target_length digits
        if len(partial) > target_length:
            partial = partial[:target_length]
        elif len(partial) < target_length:
            # Pad with random digits if needed
            partial += ''.join([str(random.randint(0, 9)) for _ in range(target_length - len(partial))])
        
        # Calculate and append Luhn checksum
        return self.calculate_luhn(partial)
    
    def generate_cvv(self, is_amex=False):
        """Generate CVV - 4 digits for AmEx, 3 digits for others"""
        if is_amex:
            return str(random.randint(1000, 9999))
        else:
            return str(random.randint(100, 999))
    
    def generate_expiry(self):
        """Generate a future expiry date"""
        year_offset = random.randint(1, 5)
        exp_year = self.current_year + year_offset
        exp_year_short = str(exp_year)[-2:]
        exp_month = str(random.randint(1, 12)).zfill(2)
        return exp_month, exp_year_short
    
    def get_bin_info(self, bin_number):
        """
        Fetch BIN information from the antipublic API.
        Uses first 6 digits for lookup but returns full info.
        """
        # Extract the first 6 digits for the BIN lookup
        bin_to_lookup = bin_number[:6] if len(bin_number) >= 6 else bin_number
        # Remove any non-digit characters just in case
        bin_to_lookup = re.sub(r'[^0-9]', '', bin_to_lookup)
        
        if not bin_to_lookup or len(bin_to_lookup) < 6:
            return None

        api_url = f"https://bins.antipublic.cc/bins/{bin_to_lookup}"
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "bin": data.get("bin", bin_to_lookup),
                    "brand": data.get("brand", "UNKNOWN"),
                    "type": data.get("type", "UNKNOWN"),
                    "level": data.get("level", "UNKNOWN"),
                    "bank": data.get("bank", "UNKNOWN"),
                    "country": data.get("country_name", "UNKNOWN"),
                    "flag": data.get("country_flag", "🏳️"),
                }
            else:
                return None
        except:
            return None
    
    def parse_input(self, input_string):
        """Parse user input in various formats"""
        input_string = input_string.strip()
        
        bin_num = None
        month = None
        year = None
        cvv = None
        
        if '|' in input_string:
            parts = input_string.split('|')
            if len(parts) >= 1:
                bin_num = parts[0].strip()
            if len(parts) >= 2 and parts[1].strip():
                month = parts[1].strip()
            if len(parts) >= 3 and parts[2].strip():
                year = parts[2].strip()
            if len(parts) >= 4 and parts[3].strip():
                cvv = parts[3].strip()
        
        elif '/' in input_string:
            parts = input_string.split('/')
            if len(parts) >= 1:
                bin_num = parts[0].strip()
            if len(parts) >= 2 and parts[1].strip():
                month = parts[1].strip()
            if len(parts) >= 3 and parts[2].strip():
                year = parts[2].strip()
            if len(parts) >= 4 and parts[3].strip():
                cvv = parts[3].strip()
        
        else:
            bin_num = input_string
        
        original_bin = bin_num
        
        if bin_num:
            bin_num = re.sub(r'[^0-9xX]', '', bin_num)
        
        if month:
            month = re.sub(r'[^0-9]', '', month)
            if month and 1 <= int(month) <= 12:
                month = month.zfill(2)
            else:
                month = None
        
        if year:
            year = re.sub(r'[^0-9]', '', year)
            if year:
                if len(year) == 4 or len(year) == 2:
                    pass
                else:
                    year = None
            else:
                year = None
        
        if cvv:
            cvv = re.sub(r'[^0-9]', '', cvv)
        
        return bin_num, month, year, cvv, original_bin
    
    def generate(self, input_pattern, count=10):
        """Generate cards and return output as list of lines with Markdown"""
        output = []
        
        parsed = self.parse_input(input_pattern)
        
        if not parsed or not parsed[0]:
            return ["❌ Invalid BIN pattern"], None
        
        bin_num, month, year, cvv, original_bin = parsed
        original_pattern = input_pattern
        is_amex = self.is_amex(bin_num)
        bin_info = self.get_bin_info(bin_num)
        display_bin = original_bin if original_bin else bin_num
        
        # Original header format
        output.append(f"*Bin* → `{display_bin}`")
        output.append(f"*Amount* → `{count}`")
        output.append("")
        
        # Generate cards
        for i in range(count):
            card = self.generate_card_number(bin_num)
            
            if month and year:
                if len(year) == 2:
                    display_year = f"20{year}"
                else:
                    display_year = year
                
                if cvv:
                    formatted_card = f"{card}|{month.zfill(2)}|{display_year}|{cvv}"
                else:
                    formatted_card = f"{card}|{month.zfill(2)}|{display_year}|{self.generate_cvv(is_amex)}"
            else:
                exp_month, exp_year = self.generate_expiry()
                formatted_card = f"{card}|{exp_month}|20{exp_year}|{self.generate_cvv(is_amex)}"
            
            output.append(f"`{formatted_card}`")
        
        output.append("")
        
        # Original BIN info format
        if bin_info:
            output.append(f"*Bin Info:* {bin_info['type']} - {bin_info['brand']} - {bin_info['level']}")
            output.append(f"*Bank:* {bin_info['bank']}")
            output.append(f"*Country:* {bin_info['country']} {bin_info['flag']}")
        else:
            output.append("*Bin Info:* N/A")
            output.append("*Bank:* N/A")
            output.append("*Country:* N/A 🏳️")
        
        return output, original_pattern

generator = CardGenerator()