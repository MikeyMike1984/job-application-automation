# app/db/mongodb.py
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import logging
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MongoDB:
    """MongoDB client for database operations."""
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize MongoDB client.
        
        Args:
            connection_string: MongoDB connection string. If not provided, uses MONGODB_URI from environment.
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.database_name = os.getenv("MONGODB_DATABASE", "job_application_system")
        self.client = None
        self.db = None
    
    async def connect(self) -> bool:
        """Connect to MongoDB.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            # Validate connection
            await self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB: {self.database_name}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_collection(self, collection_name: str):
        """Get MongoDB collection.
        
        Args:
            collection_name: Name of the collection.
            
        Returns:
            Collection object.
        """
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]

# Singleton instance
mongodb = MongoDB()