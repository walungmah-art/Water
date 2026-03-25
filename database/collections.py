# database/collections.py
"""
MongoDB collection names and schemas for reference
"""

from datetime import datetime  # Add this import

COLLECTIONS = {
    "USERS": "users",
    "PROXIES": "proxies",
    "REDEEM_CODES": "redeem_codes",
    "TRANSACTIONS": "transactions",
    "USAGE_LOGS": "usage_logs"
}

# Schema documentation (for reference only)
USER_SCHEMA = {
    "user_id": int,  # Telegram user ID
    "username": str,  # Telegram username
    "first_name": str,
    "last_name": str,
    "is_admin": bool,  # Is user admin
    "credits": int,  # Available credits
    "total_credits_used": int,  # Total credits ever used
    "created_at": datetime,  # Now datetime is defined
    "last_active": datetime,
    "is_active": bool  # If user has access
}

PROXY_SCHEMA = {
    "user_id": int,
    "proxy_string": str,  # Full proxy string
    "is_active": bool,
    "last_checked": datetime,
    "response_time": int,  # in ms
    "added_at": datetime,
    "last_used": datetime
}

REDEEM_CODE_SCHEMA = {
    "code": str,  # The redeem code
    "credits": int,  # Credits this code gives
    "created_by": int,  # Admin user_id who created it
    "created_at": datetime,
    "expires_at": datetime,  # Optional expiration
    "is_used": bool,
    "used_by": int,  # user_id who redeemed it
    "used_at": datetime,
    "is_active": bool  # Can be deactivated by admin
}

TRANSACTION_SCHEMA = {
    "user_id": int,
    "type": str,  # "redeem", "usage", "admin_add", "admin_remove"
    "credits_change": int,  # Positive or negative
    "credits_before": int,
    "credits_after": int,
    "description": str,
    "reference_code": str,  # Redeem code if applicable
    "created_at": datetime
}

USAGE_LOG_SCHEMA = {
    "user_id": int,
    "command": str,  # Command used
    "credits_cost": int,  # How many credits it cost
    "status": str,  # success/failed
    "details": dict,  # Additional details
    "created_at": datetime
}