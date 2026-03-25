# database/mongo_client.py
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from datetime import datetime, timedelta
from config_bot import MONGO_URI, MONGO_DB_NAME
from typing import Optional, Dict, List, Any
import os

logger = logging.getLogger(__name__)

class MongoDBClient:
    """Singleton MongoDB client for the bot"""
    _instance = None
    _client = None
    _db = None

    def __new__(cls, uri: str = None, db_name: str = "xman_bot"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(uri, db_name)
        return cls._instance

    def _initialize(self, uri: str, db_name: str):
        """Initialize MongoDB connection"""
        try:
            # Use URI from config or environment
            self.uri = uri or os.getenv("MONGO_URI", "mongodb+srv://blury:blury@cluster0.ahtbs9q.mongodb.net/?appName=Cluster0")
            self.db_name = db_name
            
            # Connect to MongoDB
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Verify connection
            self._client.admin.command('ping')
            self._db = self._client[self.db_name]
            
            # Create indexes for better performance
            self._create_indexes()
            
            logger.info(f"✅ Connected to MongoDB database: {self.db_name}")
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected MongoDB error: {e}")
            raise

    def _create_indexes(self):
        """Create necessary indexes for collections"""
        # Users collection indexes
        self._db.users.create_index("user_id", unique=True)
        self._db.users.create_index("username")
        self._db.users.create_index("created_at")
        self._db.users.create_index("credits")
        
        # Proxies collection indexes
        self._db.proxies.create_index([("user_id", ASCENDING), ("proxy_string", ASCENDING)], unique=True)
        self._db.proxies.create_index("last_checked")
        self._db.proxies.create_index("is_active")
        
        # Redeem codes collection indexes
        self._db.redeem_codes.create_index("code", unique=True)
        self._db.redeem_codes.create_index("created_by")
        self._db.redeem_codes.create_index([("is_used", ASCENDING), ("expires_at", ASCENDING)])
        self._db.redeem_codes.create_index("used_by")
        
        # Transactions collection indexes
        self._db.transactions.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self._db.transactions.create_index("type")
        self._db.transactions.create_index("reference_code")
        
        # Usage logs collection indexes
        self._db.usage_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self._db.usage_logs.create_index("command")
        self._db.usage_logs.create_index("created_at")

    @property
    def db(self):
        return self._db

    def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            logger.info("🔌 MongoDB connection closed")