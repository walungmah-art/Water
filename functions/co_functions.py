# functions/co_functions.py
"""
Stripe checkout parsing and information functions
"""

import re
import aiohttp
import base64
import time
from urllib.parse import unquote
from typing import Dict, Optional, Any, List

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Session management
_parser_session = None

async def get_parser_session():
    """Get or create parser session"""
    global _parser_session
    if _parser_session is None or _parser_session.closed:
        _parser_session = aiohttp.ClientSession(
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=15)
        )
    return _parser_session

async def close_parser_session():
    """Close parser session"""
    global _parser_session
    if _parser_session and not _parser_session.closed:
        await _parser_session.close()
        _parser_session = None

# Alias for backward compatibility
get_parser = get_parser_session

def escape_md(text: str) -> str:
    """Escape markdown special characters"""
    if not text:
        return ""
    special = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in special:
        text = text.replace(c, f'\\{c}')
    return text

def extract_checkout_url(text: str) -> Optional[str]:
    """Extract Stripe checkout URL from text"""
    patterns = [
        r'https?://checkout\.stripe\.com/c/pay/cs_[^\s\"\'\<\>\)]+',
        r'https?://checkout\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://buy\.stripe\.com/[^\s\"\'\<\>\)]+',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            url = m.group(0).rstrip('.,;:')
            return url
    return None

def decode_pk_from_url(url: str) -> dict:
    """
    Extract PK and CS from Stripe checkout URL hash fragment using XOR decoding
    
    Stripe encodes the PK in the URL fragment using base64 + XOR with 5
    """
    result = {"pk": None, "cs": None, "site": None}
    
    try:
        # Extract CS from URL path
        cs_match = re.search(r'(cs_(live|test)_[A-Za-z0-9]+)', url)
        if cs_match:
            result["cs"] = cs_match.group(1)
        
        # If no fragment, return what we have
        if '#' not in url:
            return result
        
        # Get the fragment part
        hash_part = url.split('#')[1]
        hash_decoded = unquote(hash_part)
        
        try:
            # The fragment often contains multiple parts
            # Try to find base64 encoded data
            import urllib.parse
            
            # URL decode first
            hash_decoded = urllib.parse.unquote(hash_part)
            
            # Try to find base64 patterns
            # Base64 strings are typically multiples of 4 and contain A-Za-z0-9+/=
            b64_pattern = r'[A-Za-z0-9+/=]{20,}'
            b64_matches = re.findall(b64_pattern, hash_decoded)
            
            for b64_str in b64_matches:
                try:
                    # Add padding if needed
                    padding = 4 - (len(b64_str) % 4)
                    if padding != 4:
                        b64_str += '=' * padding
                    
                    decoded_bytes = base64.b64decode(b64_str)
                    # XOR with 5 (Stripe's encoding)
                    xored = ''.join(chr(b ^ 5) for b in decoded_bytes)
                    
                    # Look for PK in the decoded data
                    pk_match = re.search(r'(pk_(live|test)_[A-Za-z0-9]+)', xored)
                    if pk_match:
                        result["pk"] = pk_match.group(1)
                        break
                        
                except:
                    continue
            
            # If still no PK, try the original method
            if not result["pk"]:
                try:
                    # Try to decode the entire fragment
                    hash_decoded = unquote(hash_part)
                    
                    # Sometimes the data is in a parameter
                    if 'fidkdWxOYHwnPyd1' in hash_decoded:
                        # Extract the encoded part
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(hash_decoded)
                        for key, values in parsed.items():
                            for value in values:
                                try:
                                    decoded_bytes = base64.b64decode(value)
                                    xored = ''.join(chr(b ^ 5) for b in decoded_bytes)
                                    pk_match = re.search(r'(pk_(live|test)_[A-Za-z0-9]+)', xored)
                                    if pk_match:
                                        result["pk"] = pk_match.group(1)
                                        break
                                except:
                                    continue
                except:
                    pass
                    
        except Exception:
            pass
            
    except Exception:
        pass
    
    return result

async def get_checkout_info(url: str) -> dict:
    """
    Get detailed checkout information from Stripe
    
    Returns comprehensive checkout data including:
    - PK/CS keys
    - Merchant details
    - Price and currency
    - Product information
    - Customer details
    - Payment methods accepted
    - Free trial detection
    """
    start = time.perf_counter()
    
    result = {
        "url": url,
        "pk": None,
        "cs": None,
        "merchant": None,
        "price": None,
        "currency": None,
        "product": None,
        "country": None,
        "mode": None,
        "customer_name": None,
        "customer_email": None,
        "support_email": None,
        "support_phone": None,
        "cards_accepted": None,
        "success_url": None,
        "cancel_url": None,
        "init_data": None,
        "error": None,
        "time": 0,
        "is_free_trial": False
    }
    
    try:
        # Decode PK and CS from URL
        decoded = decode_pk_from_url(url)
        result["pk"] = decoded.get("pk")
        result["cs"] = decoded.get("cs")
        
        # Check if we have CS (most important)
        if not result["cs"]:
            result["error"] = "Could not find CS token in URL"
            result["time"] = round(time.perf_counter() - start, 2)
            return result
        
        # Try to get checkout info
        session = await get_parser_session()
        
        # Try with the extracted PK if we have it
        if result["pk"]:
            body = f"key={result['pk']}&eid=NA&browser_locale=en-US&redirect_type=url"
        else:
            # Some checkouts work without PK
            body = "key=&eid=NA&browser_locale=en-US&redirect_type=url"
        
        async with session.post(
            f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
            data=body
        ) as r:
            init_data = await r.json()
        
        if "error" in init_data:
            # If failed without PK and we have PK, try with PK
            if not result["pk"] and decoded.get("pk"):
                result["pk"] = decoded.get("pk")
                body = f"key={result['pk']}&eid=NA&browser_locale=en-US&redirect_type=url"
                async with session.post(
                    f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
                    data=body
                ) as r2:
                    init_data = await r2.json()
            
            if "error" in init_data:
                result["error"] = init_data.get("error", {}).get("message", "Init failed")
                result["time"] = round(time.perf_counter() - start, 2)
                return result
        
        # Store raw init data
        result["init_data"] = init_data
        
        # Extract account settings
        account = init_data.get("account_settings", {})
        result["merchant"] = account.get("display_name") or account.get("business_name")
        result["support_email"] = account.get("support_email")
        result["support_phone"] = account.get("support_phone")
        result["country"] = account.get("country")
        
        # Extract payment details
        line_item_group = init_data.get("line_item_group")
        invoice = init_data.get("invoice")
        
        if line_item_group:
            total = line_item_group.get("total", 0)
            result["price"] = total / 100
            result["currency"] = line_item_group.get("currency", "").upper()
            result["is_free_trial"] = (total == 0)
            
            # Build product description from line items
            if line_item_group.get("line_items"):
                items = line_item_group["line_items"]
                currency = line_item_group.get("currency", "").upper()
                
                # Get currency symbol
                sym = ""
                if currency == "USD":
                    sym = "$"
                elif currency == "EUR":
                    sym = "€"
                elif currency == "GBP":
                    sym = "£"
                elif currency == "INR":
                    sym = "₹"
                
                product_parts = []
                for item in items[:3]:  # Limit to first 3 items
                    quantity = item.get("quantity", 1)
                    name = item.get("name", "Product")
                    amount = item.get("amount", 0) / 100
                    interval = item.get("recurring_interval")
                    
                    if interval:
                        product_parts.append(f"{quantity} × {name} ({sym}{amount:.2f} / {interval})")
                    else:
                        product_parts.append(f"{quantity} × {name} ({sym}{amount:.2f})")
                
                if len(items) > 3:
                    product_parts.append(f"... and {len(items)-3} more")
                
                result["product"] = ", ".join(product_parts)
        elif invoice:
            total = invoice.get("total", 0)
            result["price"] = total / 100
            result["currency"] = invoice.get("currency", "").upper()
            result["is_free_trial"] = (total == 0)
            result["product"] = invoice.get("description")
        else:
            pi = init_data.get("payment_intent") or {}
            total = pi.get("amount", 0)
            result["is_free_trial"] = (total == 0)
        
        # Determine mode (payment/subscription)
        mode = init_data.get("mode", "")
        if mode:
            result["mode"] = mode.upper()
        elif init_data.get("subscription"):
            result["mode"] = "SUBSCRIPTION"
        else:
            result["mode"] = "PAYMENT"
        
        # Extract customer info
        customer = init_data.get("customer") or {}
        result["customer_name"] = customer.get("name")
        result["customer_email"] = init_data.get("customer_email") or customer.get("email")
        
        # Extract accepted payment methods
        payment_types = init_data.get("payment_method_types") or []
        if payment_types:
            cards = [t.upper() for t in payment_types if t != "card"]
            if "card" in payment_types:
                cards.insert(0, "CARD")
            result["cards_accepted"] = ", ".join(cards) if cards else "CARD"
        
        # Extract URLs
        result["success_url"] = init_data.get("success_url")
        result["cancel_url"] = init_data.get("cancel_url")
        
    except Exception as e:
        result["error"] = str(e)
    
    result["time"] = round(time.perf_counter() - start, 2)
    return result

async def check_checkout_active(pk: str, cs: str) -> bool:
    """Check if checkout is still active"""
    try:
        session = await get_parser_session()
        body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
        
        async with session.post(
            f"https://api.stripe.com/v1/payment_pages/{cs}/init",
            data=body,
            timeout=aiohttp.ClientTimeout(total=5)
        ) as response:
            data = await response.json()
            return "error" not in data
    except Exception:
        return False

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "RUB": "₽", "BRL": "R$", "CAD": "C$",
        "AUD": "A$", "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "THB": "฿",
        "VND": "₫", "PHP": "₱", "IDR": "Rp", "MYR": "RM", "ZAR": "R",
        "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł",
        "TRY": "₺", "AED": "د.إ", "SAR": "﷼", "ILS": "₪", "TWD": "NT$"
    }
    return symbols.get(currency, "")

# Legacy function for backward compatibility
async def parse_stripe_checkout(url: str) -> dict:
    """Parse Stripe checkout URL (legacy - minimal version)"""
    result = await get_checkout_info(url)
    
    # Return minimal format for backward compatibility
    return {
        "url": result["url"],
        "pk": result["pk"],
        "cs": result["cs"],
        "merchant": result["merchant"],
        "price": result["price"],
        "currency": result["currency"],
        "product": result["product"],
        "error": result["error"]
    }

def format_checkout_md(data: dict) -> str:
    """Format checkout data as markdown"""
    if data.get("error"):
        return f"❌ `{escape_md(data['error'])}`"
    
    lines = ["⚡ *Stripe Checkout*", ""]
    
    if data.get("merchant"):
        lines.append(f"🏪 *Merchant:* `{escape_md(data['merchant'])}`")
    
    if data.get("product"):
        lines.append(f"📦 *Product:* `{escape_md(data['product'][:50])}`")
    
    if data.get("price") is not None:
        sym = get_currency_symbol(data.get("currency", ""))
        lines.append(f"💰 *Price:* `{sym}{data['price']:.2f} {data.get('currency', '')}`")
    elif data.get("is_free_trial"):
        lines.append(f"🎁 *Price:* `FREE TRIAL`")
    
    lines.append("")
    
    if data.get("pk"):
        pk_short = data['pk'][:20] + "..." if len(data['pk']) > 20 else data['pk']
        lines.append(f"🔑 *PK:* `{escape_md(pk_short)}`")
    
    if data.get("cs"):
        cs_short = data['cs'][:20] + "..." if len(data['cs']) > 20 else data['cs']
        lines.append(f"🎫 *CS:* `{escape_md(cs_short)}`")
    
    return "\n".join(lines)

def add_blockquote(text: str) -> str:
    """Add blockquote formatting to text"""
    return "\n".join(f">{line}" for line in text.split("\n"))

# Export all functions
__all__ = [
    'escape_md',
    'extract_checkout_url',
    'decode_pk_from_url',
    'parse_stripe_checkout',
    'get_checkout_info',
    'get_currency_symbol',
    'check_checkout_active',
    'format_checkout_md',
    'add_blockquote',
    'get_parser_session',
    'get_parser',
    'close_parser_session',
]