# database/__init__.py
"""
Database package for MongoDB integration
"""

from .mongo_client import MongoDBClient
from .repositories import (
    UserRepository,
    ProxyRepository,
    RedeemCodeRepository,
    TransactionRepository,
    UsageLogRepository
)
from .collections import COLLECTIONS

__all__ = [
    'MongoDBClient',
    'UserRepository',
    'ProxyRepository',
    'RedeemCodeRepository',
    'TransactionRepository',
    'UsageLogRepository',
    'COLLECTIONS'
]