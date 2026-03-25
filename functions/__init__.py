# functions/__init__.py
"""
Core functions package for Stripe checkout bot
Contains all business logic for card parsing, charging, and checkout operations
"""

# Import from card_utils
from .card_utils import (
    parse_card,
    parse_cards,
    format_card,
    CARD_PATTERN,
    mask_card,
    detect_card_brand,
    validate_luhn,
    validate_expiry,
    validate_cvv,
    validate_card
)

# Import from charge_functions
from .charge_functions import (
    get_session,
    close_session,
    init_checkout,
    charge_card,
    charge_card_fast,
    handle_free_trial,
    ChargeStatus,
    BypassMethod,
    HEADERS as CHARGE_HEADERS
)

# Import from co_functions
from .co_functions import (
    escape_md,
    extract_checkout_url,
    decode_pk_from_url,
    parse_stripe_checkout,
    get_checkout_info,
    get_currency_symbol,
    check_checkout_active,
    format_checkout_md,
    add_blockquote,
    close_parser_session,
    HEADERS as CO_HEADERS
)

# Import from proxy_utils
from .proxy_utils import (
    parse_proxy_format,
    get_proxy_url,
    obfuscate_ip,
    load_proxies,
    save_proxies,
    get_user_proxies,
    get_user_proxy,
    add_user_proxy,
    remove_user_proxy,
    check_proxy_alive,
    check_proxies_batch,
    get_proxy_info,
    load_users,
    save_users,
    is_allowed_user,
    add_allowed_user,
    remove_allowed_user,
    check_access,
    format_proxy_list
)

# Import from bin_utils
from .bin_utils import (
    luhn_checksum,
    generate_luhn_card,
    detect_card_brand as detect_bin_brand,
    generate_expiry_date,
    generate_cvv,
    generate_next_card,
    format_card_for_display,
    get_card_info,
    batch_generate_cards
)

# Import from stripe_checkout
from .stripe_checkout import (
    create_session,
    get_nonce,
    register_account,
    post_billing_address,
    get_add_payment_page_and_nonces,
    check_bin,
    create_stripe_payment_method,
    attach_payment_method_to_site,
    parse_card_line,
    parse_card_components,
    format_card_display,
    format_result_message,
    process_single_card
)

# Import from card_generator (NEW)
from .card_generator import (
    generator,
    CardGenerator
)

# Version info
__version__ = "2.3.0"  # Updated version

# Export all commonly used items
__all__ = [
    # Card utilities
    'parse_card',
    'parse_cards',
    'format_card',
    'CARD_PATTERN',
    'mask_card',
    'detect_card_brand',
    'validate_luhn',
    'validate_expiry',
    'validate_cvv',
    'validate_card',
    
    # Charge functions
    'get_session',
    'close_session',
    'init_checkout',
    'charge_card',
    'charge_card_fast',
    'handle_free_trial',
    'ChargeStatus',
    'BypassMethod',
    'CHARGE_HEADERS',
    
    # Checkout functions
    'escape_md',
    'extract_checkout_url',
    'decode_pk_from_url',
    'parse_stripe_checkout',
    'get_checkout_info',
    'get_currency_symbol',
    'check_checkout_active',
    'format_checkout_md',
    'add_blockquote',
    'close_parser_session',
    'CO_HEADERS',
    
    # Proxy utilities
    'parse_proxy_format',
    'get_proxy_url',
    'obfuscate_ip',
    'load_proxies',
    'save_proxies',
    'get_user_proxies',
    'get_user_proxy',
    'add_user_proxy',
    'remove_user_proxy',
    'check_proxy_alive',
    'check_proxies_batch',
    'get_proxy_info',
    'load_users',
    'save_users',
    'is_allowed_user',
    'add_allowed_user',
    'remove_allowed_user',
    'check_access',
    'format_proxy_list',
    
    # BIN utilities
    'luhn_checksum',
    'generate_luhn_card',
    'detect_bin_brand',
    'generate_expiry_date',
    'generate_cvv',
    'generate_next_card',
    'format_card_for_display',
    'get_card_info',
    'batch_generate_cards',
    
    # Stripe checkout functions
    'create_session',
    'get_nonce',
    'register_account',
    'post_billing_address',
    'get_add_payment_page_and_nonces',
    'check_bin',
    'create_stripe_payment_method',
    'attach_payment_method_to_site',
    'parse_card_line',
    'parse_card_components',
    'format_card_display',
    'format_result_message',
    'process_single_card',
    
    # Card generator functions (NEW)
    'generator',
    'CardGenerator',
]

# Define ChargeStatus enum for better type safety
class ChargeStatus:
    """Charge status constants"""
    CHARGED = "CHARGED"
    DECLINED = "DECLINED"
    THREE_DS = "3DS"
    THREE_DS_SKIP = "3DS SKIP"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

class BypassMethod:
    """Bypass method constants"""
    NONE = "none"
    RETURN_URL = "return_url"
    PAYMENT_INTENT = "payment_intent"
    SETUP_FUTURE = "setup_future"
    OFF_SESSION = "off_session"
    MANUAL = "manual"
    INCREMENTAL = "incremental"