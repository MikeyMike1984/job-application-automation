# scripts/setup_mongodb.py
import asyncio
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.core.logging import logger
from app.db.mongodb import mongodb

async def setup_mongodb():
    """Test MongoDB connection and set up initial collections."""
    print(f"Connecting to MongoDB at: {settings.DATABASE.URI}")
    print(f"Database name: {settings.DATABASE.NAME}")
    
    connected = await mongodb.connect()
    if connected:
        print("Successfully connected to MongoDB!")
        
        # Create test collection
        collection = mongodb.get_collection("test_collection")
        result = await collection.insert_one({"test": True, "timestamp": "setup_test"})
        print(f"Created test document with ID: {result.inserted_id}")
        
        # List all collections
        collections = await mongodb.db.list_collection_names()
        print(f"Collections in database: {collections}")
        
        # Clean up
        await collection.delete_many({"test": True})
        print("Test document removed")
        
        await mongodb.disconnect()
        print("MongoDB connection closed")
        return True
    else:
        print("Failed to connect to MongoDB! Check your connection string and credentials.")
        return False

if __name__ == "__main__":
    asyncio.run(setup_mongodb())