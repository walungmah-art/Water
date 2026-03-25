# middleware/logging.py
"""
Logging middleware to track command usage
"""

from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
import logging
import time
from datetime import datetime

from database.repositories import UsageLogRepository

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """Middleware to log all command usage"""
    
    def __init__(self):
        self.usage_repo = UsageLogRepository()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Skip if not a message
        if not event.text:
            return await handler(event, data)
        
        start_time = time.time()
        user_id = event.from_user.id
        command = event.text.split()[0].lower()
        
        # Process the command
        try:
            result = await handler(event, data)
            elapsed = time.time() - start_time
            
            # Log successful command
            self._log_command(user_id, command, "success", elapsed, data)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            # Log failed command
            self._log_command(user_id, command, "error", elapsed, data, error=str(e))
            logger.error(f"Error processing command {command} for user {user_id}: {e}")
            raise
    
    def _log_command(self, user_id: int, command: str, status: str, 
                     elapsed: float, data: Dict, error: str = None):
        """Log command to database"""
        try:
            log_entry = {
                "user_id": user_id,
                "command": command,
                "status": status,
                "elapsed": round(elapsed, 2),
                "credits_used": data.get("required_credits", 0),
                "bypass_strength": data.get("bypass_strength", "none"),
                "timestamp": datetime.now()
            }
            if error:
                log_entry["error"] = error[:100]
            
            self.usage_repo.log_usage(
                user_id=user_id,
                command=command,
                credits_cost=log_entry["credits_used"],
                status=status,
                details=log_entry
            )
        except Exception as e:
            logger.error(f"Failed to log command: {e}")