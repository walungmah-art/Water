# database/repositories.py
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from pymongo.errors import DuplicateKeyError
import logging
import random
import string

from database.mongo_client import MongoDBClient

logger = logging.getLogger(__name__)

class UserRepository:
    """Repository for user operations with credit system"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["users"]
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Add or update a user"""
        try:
            result = self.collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "last_active": datetime.now()
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "is_admin": False,
                        "credits": 0,
                        "total_credits_used": 0,
                        "created_at": datetime.now(),
                        "is_active": False
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return self.collection.find_one({"user_id": user_id}, {"_id": 0})
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        user = self.get_user(user_id)
        return user.get("is_admin", False) if user else False
    
    def set_admin(self, user_id: int, admin: bool = True) -> bool:
        """Set user's admin status"""
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": admin}}
        )
        return result.modified_count > 0
    
    def is_active(self, user_id: int) -> bool:
        """Check if user has active access"""
        user = self.get_user(user_id)
        return user.get("is_active", False) if user else False
    
    def set_active(self, user_id: int, active: bool = True) -> bool:
        """Set user's active status"""
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": active}}
        )
        return result.modified_count > 0
    
    def get_credits(self, user_id: int) -> int:
        """Get user's available credits"""
        user = self.get_user(user_id)
        return user.get("credits", 0) if user else 0
    
    def add_credits(self, user_id: int, amount: int, description: str = "") -> Tuple[bool, int, int]:
        """Add credits to user account. Returns (success, credits_before, credits_after)"""
        user = self.get_user(user_id)
        if not user:
            self.add_user(user_id)
            user = {"credits": 0}
        
        credits_before = user.get("credits", 0)
        credits_after = credits_before + amount
        
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"credits": credits_after}}
        )
        
        if result.modified_count > 0:
            # Log transaction
            TransactionRepository().add_transaction({
                "user_id": user_id,
                "type": "admin_add" if amount > 0 else "admin_remove",
                "credits_change": amount,
                "credits_before": credits_before,
                "credits_after": credits_after,
                "description": description,
                "created_at": datetime.now()
            })
            return True, credits_before, credits_after
        return False, credits_before, credits_before
    
    def use_credits(self, user_id: int, amount: int, command: str, details: dict = None) -> Tuple[bool, int, int]:
        """Use credits for a command. Returns (success, credits_before, credits_after)"""
        user = self.get_user(user_id)
        if not user:
            return False, 0, 0
        
        credits_before = user.get("credits", 0)
        if credits_before < amount:
            return False, credits_before, credits_before
        
        credits_after = credits_before - amount
        total_used = user.get("total_credits_used", 0) + amount
        
        result = self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "credits": credits_after,
                    "total_credits_used": total_used
                }
            }
        )
        
        if result.modified_count > 0:
            # Log transaction
            TransactionRepository().add_transaction({
                "user_id": user_id,
                "type": "usage",
                "credits_change": -amount,
                "credits_before": credits_before,
                "credits_after": credits_after,
                "description": f"Used {command}",
                "created_at": datetime.now()
            })
            
            # Log usage
            UsageLogRepository().log_usage(
                user_id=user_id,
                command=command,
                credits_cost=amount,
                status="success",
                details=details
            )
            return True, credits_before, credits_after
        return False, credits_before, credits_before
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        return list(self.collection.find({}, {"_id": 0}))
    
    def get_active_users(self) -> List[Dict]:
        """Get active users"""
        return list(self.collection.find({"is_active": True}, {"_id": 0}))
    
    def get_users_with_credits(self) -> List[Dict]:
        """Get users with credits > 0"""
        return list(self.collection.find({"credits": {"$gt": 0}}, {"_id": 0}))


class ProxyRepository:
    """Repository for proxy operations"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["proxies"]
    
    def add_proxy(self, user_id: int, proxy_string: str) -> bool:
        """Add a proxy for user"""
        try:
            result = self.collection.update_one(
                {"user_id": user_id, "proxy_string": proxy_string},
                {
                    "$setOnInsert": {
                        "user_id": user_id,
                        "proxy_string": proxy_string,
                        "is_active": True,
                        "added_at": datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except DuplicateKeyError:
            return False
        except Exception as e:
            logger.error(f"Error adding proxy for user {user_id}: {e}")
            return False
    
    def remove_proxy(self, user_id: int, proxy_string: str = None) -> int:
        """Remove a proxy or all proxies for user. Returns number deleted."""
        query = {"user_id": user_id}
        if proxy_string and proxy_string.lower() != "all":
            query["proxy_string"] = proxy_string
        
        result = self.collection.delete_many(query)
        return result.deleted_count
    
    def get_user_proxies(self, user_id: int, active_only: bool = True) -> List[str]:
        """Get all proxies for a user"""
        query = {"user_id": user_id}
        if active_only:
            query["is_active"] = True
        
        cursor = self.collection.find(query, {"proxy_string": 1, "_id": 0})
        return [doc["proxy_string"] for doc in cursor]
    
    def get_random_proxy(self, user_id: int) -> Optional[str]:
        """Get a random active proxy for user"""
        pipeline = [
            {"$match": {"user_id": user_id, "is_active": True}},
            {"$sample": {"size": 1}}
        ]
        result = list(self.collection.aggregate(pipeline))
        return result[0]["proxy_string"] if result else None
    
    def update_proxy_status(self, proxy_string: str, is_active: bool, response_time: Union[float, int, None] = None):
        """
        Update proxy status after checking
        Now accepts float response_time to handle decimal values like 637.77ms
        """
        update = {"$set": {"is_active": is_active, "last_checked": datetime.now()}}
        if response_time is not None:
            # Store as float to preserve decimal precision
            update["$set"]["response_time"] = float(response_time) if response_time else None
        
        self.collection.update_many(
            {"proxy_string": proxy_string},
            update
        )
    
    def update_last_used(self, user_id: int, proxy_string: str):
        """Update last used timestamp for a proxy"""
        self.collection.update_one(
            {"user_id": user_id, "proxy_string": proxy_string},
            {"$set": {"last_used": datetime.now()}}
        )


class RedeemCodeRepository:
    """Repository for redeem code operations"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["redeem_codes"]
    
    def generate_code(self, length: int = 10) -> str:
        """Generate a random alphanumeric code"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))
    
    def create_codes(self, admin_id: int, credits: int, count: int, expires_in_days: int = None) -> List[str]:
        """Generate multiple redeem codes"""
        codes = []
        for _ in range(count):
            code = self.generate_code()
            code_doc = {
                "code": code,
                "credits": credits,
                "created_by": admin_id,
                "created_at": datetime.now(),
                "is_used": False,
                "is_active": True
            }
            if expires_in_days:
                code_doc["expires_at"] = datetime.now() + timedelta(days=expires_in_days)
            
            try:
                self.collection.insert_one(code_doc)
                codes.append(code)
            except DuplicateKeyError:
                # Very unlikely, but try once more
                code = self.generate_code()
                code_doc["code"] = code
                self.collection.insert_one(code_doc)
                codes.append(code)
        
        return codes
    
    def validate_code(self, code: str) -> Optional[Dict]:
        """Check if a code is valid and not used"""
        query = {
            "code": code,
            "is_used": False,
            "is_active": True
        }
        # Check expiration if exists
        code_doc = self.collection.find_one(query)
        if code_doc and code_doc.get("expires_at"):
            if code_doc["expires_at"] < datetime.now():
                return None
        return code_doc
    
    def redeem_code(self, code: str, user_id: int) -> Tuple[bool, int, str]:
        """
        Redeem a code for a user.
        Returns (success, credits_gained, message)
        """
        code_doc = self.validate_code(code)
        if not code_doc:
            return False, 0, "Invalid or expired code"
        
        # Mark as used
        self.collection.update_one(
            {"code": code},
            {
                "$set": {
                    "is_used": True,
                    "used_by": user_id,
                    "used_at": datetime.now()
                }
            }
        )
        
        credits = code_doc["credits"]
        
        # Add credits to user
        user_repo = UserRepository()
        user_repo.add_user(user_id)  # Ensure user exists
        success, before, after = user_repo.add_credits(
            user_id, 
            credits, 
            f"Redeemed code: {code}"
        )
        
        if success:
            # Activate user if not already active
            user_repo.set_active(user_id, True)
            
            # Log transaction
            TransactionRepository().add_transaction({
                "user_id": user_id,
                "type": "redeem",
                "credits_change": credits,
                "credits_before": before,
                "credits_after": after,
                "description": f"Redeemed code: {code}",
                "reference_code": code,
                "created_at": datetime.now()
            })
            
            return True, credits, f"Successfully redeemed {credits} credits"
        else:
            return False, 0, "Error adding credits to account"
    
    def deactivate_code(self, code: str) -> Tuple[bool, str]:
        """Deactivate a code (admin command)"""
        code_doc = self.collection.find_one({"code": code})
        if not code_doc:
            return False, "Code not found"
        
        self.collection.update_one(
            {"code": code},
            {"$set": {"is_active": False}}
        )
        
        return True, "Code deactivated successfully"
    
    def get_all_codes(self, include_used: bool = False) -> List[Dict]:
        """Get all redeem codes"""
        query = {} if include_used else {"is_used": False}
        return list(self.collection.find(query, {"_id": 0}).sort("created_at", -1))
    
    def get_stats(self) -> Dict:
        """Get statistics about redeem codes"""
        pipeline = [
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "used": {"$sum": {"$cond": [{"$eq": ["$is_used", True]}, 1, 0]}},
                "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}},
                "total_credits": {"$sum": "$credits"},
                "redeemed_credits": {"$sum": {"$cond": [{"$eq": ["$is_used", True]}, "$credits", 0]}}
            }}
        ]
        result = list(self.collection.aggregate(pipeline))
        return result[0] if result else {
            "total": 0, "used": 0, "active": 0, 
            "total_credits": 0, "redeemed_credits": 0
        }


class TransactionRepository:
    """Repository for transaction records"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["transactions"]
    
    def add_transaction(self, transaction_data: Dict) -> str:
        """Record a transaction"""
        result = self.collection.insert_one(transaction_data)
        return str(result.inserted_id)
    
    def get_user_transactions(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a user"""
        cursor = self.collection.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return list(cursor)
    
    def get_all_transactions(self, limit: int = 100) -> List[Dict]:
        """Get recent transactions (admin)"""
        cursor = self.collection.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return list(cursor)


class StatsRepository:
    """Repository for bot-wide statistics"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["stats"]
    
    async def update_daily_stats(self):
        """Update or create today's daily stats record"""
        from datetime import date
        today = date.today().isoformat()
        self.collection.update_one(
            {"date": today},
            {"$setOnInsert": {"date": today, "commands_run": 0, "users_active": 0}},
            upsert=True
        )
    
    def increment_command(self, command: str):
        """Increment command count for today"""
        from datetime import date
        today = date.today().isoformat()
        self.collection.update_one(
            {"date": today},
            {"$inc": {"commands_run": 1, f"commands.{command.strip('/')}": 1}},
            upsert=True
        )
    
    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """Get stats for the last N days"""
        cursor = self.collection.find({}, {"_id": 0}).sort("date", -1).limit(days)
        return list(cursor)
    
    def get_total_stats(self) -> Dict:
        """Get aggregated total stats"""
        pipeline = [
            {"$group": {
                "_id": None,
                "total_commands": {"$sum": "$commands_run"},
                "total_days": {"$sum": 1}
            }}
        ]
        result = list(self.collection.aggregate(pipeline))
        return result[0] if result else {"total_commands": 0, "total_days": 0}


class UsageLogRepository:
    """Repository for command usage logs"""
    
    def __init__(self):
        self.db = MongoDBClient().db
        self.collection = self.db["usage_logs"]
    
    def log_usage(self, user_id: int, command: str, credits_cost: int, 
                  status: str, details: dict = None):
        """Log command usage"""
        log_entry = {
            "user_id": user_id,
            "command": command,
            "credits_cost": credits_cost,
            "status": status,
            "details": details or {},
            "created_at": datetime.now()
        }
        self.collection.insert_one(log_entry)
    
    def get_user_usage(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get usage logs for a user"""
        cursor = self.collection.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return list(cursor)
    
    def get_command_stats(self, days: int = 7) -> Dict:
        """Get statistics about command usage"""
        since = datetime.now() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": "$command",
                "count": {"$sum": 1},
                "total_credits": {"$sum": "$credits_cost"}
            }},
            {"$sort": {"count": -1}}
        ]
        return list(self.collection.aggregate(pipeline))