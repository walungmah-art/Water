# middleware/rate_limit.py
"""
Rate limiting middleware to prevent abuse
"""

from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
import time
import asyncio
from collections import defaultdict
import logging

from config_bot import RATE_LIMIT_ENABLED, RATE_LIMIT, RATE_LIMIT_WINDOW, OWNER_ID

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseMiddleware):
    """Middleware to rate limit user requests"""
    
    def __init__(self):
        self.user_requests = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Skip if rate limiting disabled
        if not RATE_LIMIT_ENABLED:
            return await handler(event, data)
        
        # Skip if not a message
        if not event.text:
            return await handler(event, data)
        
        user_id = event.from_user.id
        
        # Skip rate limiting for owner
        if user_id == OWNER_ID:
            return await handler(event, data)
        
        async with self.lock:
            now = time.time()
            
            # Clean old requests
            self.user_requests[user_id] = [
                req_time for req_time in self.user_requests[user_id]
                if now - req_time < RATE_LIMIT_WINDOW
            ]
            
            # Check rate limit
            if len(self.user_requests[user_id]) >= RATE_LIMIT:
                await event.answer(
                    f"⚠️ <b>Rate Limit Exceeded</b>\n\n"
                    f"You can only use {RATE_LIMIT} commands per {RATE_LIMIT_WINDOW} seconds.\n"
                    f"Please wait a moment before trying again.",
                    parse_mode="HTML"
                )
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return
            
            # Add current request
            self.user_requests[user_id].append(now)
        
        return await handler(event, data)