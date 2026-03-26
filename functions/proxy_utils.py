# functions/proxy_utils.py
"""
Proxy management utilities for Stripe checkout bot with MongoDB integration
"""

import json
import os
import random
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from config_bot import PROXY_FILE, ALLOWED_GROUP, OWNER_ID
from aiogram.types import Message

# Import MongoDB repositories
from database.repositories import UserRepository, ProxyRepository

# Initialize repositories
user_repo = UserRepository()
proxy_repo = ProxyRepository()

# ========== PROXY PARSING ==========

def parse_proxy_format(proxy_str: str) -> Dict[str, Any]:
    """
    Parse proxy string into components
    
    Supported formats:
    - host:port:user:pass
    - user:pass@host:port
    - host:port
    """
    proxy_str = proxy_str.strip()
    result = {
        "user": None, 
        "password": None, 
        "host": None, 
        "port": None, 
        "raw": proxy_str,
        "type": "http"
    }
    
    try:
        # Format: user:pass@host:port
        if '@' in proxy_str:
            if proxy_str.count('@') == 1:
                auth_part, host_part = proxy_str.rsplit('@', 1)
                if ':' in auth_part:
                    result["user"], result["password"] = auth_part.split(':', 1)
                if ':' in host_part:
                    result["host"], port_str = host_part.rsplit(':', 1)
                    result["port"] = int(port_str)
        
        # Format: host:port:user:pass or host:port
        else:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                result["host"] = parts[0]
                result["port"] = int(parts[1])
                result["user"] = parts[2]
                result["password"] = parts[3]
            elif len(parts) == 2:
                result["host"] = parts[0]
                result["port"] = int(parts[1])
    except Exception:
        pass
    
    return result

def get_proxy_url(proxy_str: str) -> Optional[str]:
    """Convert proxy string to URL format"""
    parsed = parse_proxy_format(proxy_str)
    if parsed["host"] and parsed["port"]:
        if parsed["user"] and parsed["password"]:
            return f"http://{parsed['user']}:{parsed['password']}@{parsed['host']}:{parsed['port']}"
        else:
            return f"http://{parsed['host']}:{parsed['port']}"
    return None

def obfuscate_ip(ip: str) -> str:
    """Obfuscate IP for display (privacy)"""
    if not ip:
        return "N/A"
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0][0]}XX.{parts[1][0]}XX.{parts[2][0]}XX.{parts[3][0]}XX"
    return "N/A"

# ========== PROXY STORAGE (MongoDB) ==========

def load_proxies() -> Dict:
    """Load proxies from JSON file (backward compatibility)"""
    if os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_proxies(data: Dict):
    """Save proxies to JSON file (backward compatibility)"""
    try:
        with open(PROXY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving proxies: {e}")

def get_user_proxies(user_id: int) -> List[str]:
    """Get all proxies for a user from MongoDB"""
    return proxy_repo.get_user_proxies(user_id)

def get_user_proxy(user_id: int) -> Optional[str]:
    """Get a random proxy for user from MongoDB"""
    return proxy_repo.get_random_proxy(user_id)

def add_user_proxy(user_id: int, proxy: str):
    """Add a proxy for user in MongoDB"""
    proxy_repo.add_proxy(user_id, proxy)
    
    # Update stats
    try:
        from commands.admin import update_stats
        update_stats(proxy_added=True)
    except:
        pass

def remove_user_proxy(user_id: int, proxy: str = None) -> bool:
    """Remove a proxy for user from MongoDB"""
    count = proxy_repo.remove_proxy(user_id, proxy)
    return count > 0

# ========== PROXY CHECKING ==========

async def check_proxy_alive(proxy_str: str, timeout: int = 10) -> Dict[str, Any]:
    """Check if a proxy is alive and update status in MongoDB"""
    result = {
        "proxy": proxy_str,
        "status": "dead",
        "response_time": None,
        "external_ip": None,
        "error": None
    }
    
    proxy_url = get_proxy_url(proxy_str)
    if not proxy_url:
        result["error"] = "Invalid format"
        return result
    
    try:
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://ip-api.com/json",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                elapsed = round((time.perf_counter() - start) * 1000, 2)
                
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "alive"
                    result["response_time"] = f"{elapsed}ms"
                    result["external_ip"] = data.get("query")
                else:
                    result["error"] = f"HTTP {resp.status}"
                    
    except asyncio.TimeoutError:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:50]
    
    # Update status in MongoDB - FIXED VERSION
    is_alive = (result["status"] == "alive")
    response_time = None
    if result.get("response_time"):
        # Remove 'ms' and convert to float properly
        time_str = result["response_time"].replace("ms", "")
        try:
            # Convert to float first (handles decimal values like '637.77')
            response_time = float(time_str)
            # Round to nearest integer if you want to store as int
            # response_time = int(round(float(time_str)))
        except ValueError:
            response_time = 0
    
    proxy_repo.update_proxy_status(proxy_str, is_alive, response_time)
    
    return result

async def check_proxies_batch(proxies: List[str], max_concurrent: int = 10) -> List[Dict]:
    """Check multiple proxies concurrently"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_with_semaphore(proxy):
        async with semaphore:
            return await check_proxy_alive(proxy)
    
    tasks = [check_with_semaphore(p) for p in proxies]
    return await asyncio.gather(*tasks)

async def get_proxy_info(proxy_str: str = None, timeout: int = 10) -> Dict[str, Any]:
    """Get information about proxy or direct connection"""
    result = {
        "status": "dead",
        "ip": None,
        "ip_obfuscated": None,
        "country": None,
        "city": None,
        "org": None,
        "using_proxy": False
    }
    
    proxy_url = None
    if proxy_str:
        proxy_url = get_proxy_url(proxy_str)
        result["using_proxy"] = True
    
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=timeout)}
            if proxy_url:
                kwargs["proxy"] = proxy_url
            
            async with session.get("http://ip-api.com/json", **kwargs) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "alive"
                    result["ip"] = data.get("query")
                    result["ip_obfuscated"] = obfuscate_ip(data.get("query"))
                    result["country"] = data.get("country")
                    result["city"] = data.get("city")
                    result["org"] = data.get("isp")
    except Exception:
        result["status"] = "dead"
    
    return result

# ========== ACCESS CONTROL (MongoDB) ==========

def load_users() -> List[int]:
    """Load allowed users from MongoDB"""
    users = user_repo.get_all_users()
    return [u["user_id"] for u in users if u.get("is_allowed", False)]

def save_users(users: List[int]):
    """Save allowed users to MongoDB - kept for compatibility"""
    # This function is kept for backward compatibility
    # Actual user management should use the repositories directly
    pass

def is_allowed_user(user_id: int) -> bool:
    """
    Check if user is specifically allowed (for paid features)
    This is separate from basic access
    """
    user = user_repo.get_user(user_id)
    return user.get("is_allowed", False) if user else False

def add_allowed_user(user_id: int):
    """Add user to allowed list in MongoDB (for paid features)"""
    # First ensure user exists
    user_repo.add_user(user_id)
    # Then set allowed to True
    from database.mongo_client import MongoDBClient
    db = MongoDBClient().db
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_allowed": True}}
    )

def remove_allowed_user(user_id: int):
    """Remove user from allowed list in MongoDB"""
    from database.mongo_client import MongoDBClient
    db = MongoDBClient().db
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_allowed": False}}
    )

def check_basic_access(msg: Message) -> bool:
    """
    Check if user has basic access to use the bot.
    This allows ALL users to use free commands.
    Only paid features require is_allowed_user check.
    """
    # Group access - if specified group, anyone in that group has access
    if msg.chat.id == ALLOWED_GROUP:
        return True
    
    # Private chat - ALL users are allowed for free commands
    if msg.chat.type == "private":
        return True
    
    return False

# Keep the old function name for backward compatibility but redirect
def check_access(msg: Message) -> bool:
    """
    Legacy function - now just returns True for all private chats
    Specific permission checks should be done in middleware/commands
    """
    if msg.chat.type == "private":
        return True
    if msg.chat.id == ALLOWED_GROUP:
        return True
    return False

def check_paid_access(msg: Message) -> bool:
    """
    Check if user has access to paid/premium commands.
    Alias for check_access with same logic.
    """
    return check_access(msg)

# ========== HELPER FUNCTIONS ==========

def format_proxy_list(proxies: List[str], max_display: int = 10) -> str:
    """Format proxy list for display"""
    if not proxies:
        return "    • <code>None</code>"
    
    lines = []
    for p in proxies[:max_display]:
        lines.append(f"    • <code>{p}</code>")
    
    if len(proxies) > max_display:
        lines.append(f"    • <code>... and {len(proxies) - max_display} more</code>")
    
    return "\n".join(lines)

# ========== MIGRATION FUNCTION ==========

async def migrate_from_json_to_mongodb():
    """Migrate existing proxy data from JSON to MongoDB"""
    print("🔄 Migrating proxies from JSON to MongoDB...")
    
    # Load from JSON
    json_proxies = load_proxies()
    migrated_count = 0
    
    for user_id_str, proxy_list in json_proxies.items():
        user_id = int(user_id_str)
        
        if isinstance(proxy_list, str):
            proxy_list = [proxy_list]
        
        for proxy_str in proxy_list:
            # Check if already exists in MongoDB
            existing = proxy_repo.get_user_proxies(user_id)
            if proxy_str not in existing:
                proxy_repo.add_proxy(user_id, proxy_str)
                migrated_count += 1
    
    print(f"✅ Migrated {migrated_count} proxies to MongoDB")
    return migrated_count
