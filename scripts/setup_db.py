#!/usr/bin/env python
# scripts/setup_db.py
import asyncio
import sys
import os
from typing import List

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.core.logging import logger
from app.db.mongodb import mongodb

async def create_collections():
    """Create collections with appropriate indexes."""
    if not mongodb.db:
        connected = await mongodb.connect()
        if not connected:
            logger.error("Failed to connect to MongoDB")
            return False
    
    # Create jobs collection with indexes
    jobs_collection = mongodb.get_collection("jobs")
    
    # Create indexes for jobs collection
    await jobs_collection.create_index("source")
    await jobs_collection.create_index("company_name")
    await jobs_collection.create_index("status")
    await jobs_collection.create_index("date_posted")
    await jobs_collection.create_index("date_scraped")
    await jobs_collection.create_index([("title", "text"), ("description", "text")])  # Text search
    
    logger.info("Created jobs collection with indexes")
    
    # Create profiles collection with indexes
    profiles_collection = mongodb.get_collection("profiles")
    
    # Create indexes for profiles collection
    await profiles_collection.create_index("contact.email", unique=True)
    await profiles_collection.create_index("name.last")
    await profiles_collection.create_index("skills.name")
    
    logger.info("Created profiles collection with indexes")
    
    # Create resumes collection with indexes
    resumes_collection = mongodb.get_collection("resumes")
    
    # Create indexes for resumes collection
    await resumes_collection.create_index("user_id")
    await resumes_collection.create_index("job_id")
    await resumes_collection.create_index("created_at")
    
    logger.info("Created resumes collection with indexes")
    
    # Create applications collection with indexes
    applications_collection = mongodb.get_collection("applications")
    
    # Create indexes for applications collection
    await applications_collection.create_index([("user_id", 1), ("job_id", 1)], unique=True)
    await applications_collection.create_index("status")
    await applications_collection.create_index("created_at")
    
    logger.info("Created applications collection with indexes")
    
    return True

async def clean_database():
    """Clean the database for testing."""
    if not mongodb.db:
        connected = await mongodb.connect()
        if not connected:
            logger.error("Failed to connect to MongoDB")
            return False
    
    # Ask for confirmation
    confirm = input(f"This will DELETE ALL DATA in the '{settings.DATABASE.NAME}' database. Type 'YES' to confirm: ")
    if confirm != "YES":
        logger.info("Database cleanup aborted")
        return False
    
    # Drop all collections
    collections = await mongodb.db.list_collection_names()
    for collection_name in collections:
        await mongodb.db.drop_collection(collection_name)
    
    logger.info(f"Cleaned database '{settings.DATABASE.NAME}'")
    return True

async def main():
    """Main function to set up or clean database."""
    print("\nMongoDB Database Setup Utility")
    print("==============================")
    print(f"Database: {settings.DATABASE.NAME}")
    print(f"URI: {settings.DATABASE.URI}")
    print("\nOptions:")
    print("1. Set up collections and indexes")
    print("2. Clean database (delete all data)")
    print("3. Both (clean and set up)")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ")
    
    if choice == "1":
        success = await create_collections()
        if success:
            logger.info("Database setup completed successfully")
    elif choice == "2":
        success = await clean_database()
        if success:
            logger.info("Database cleanup completed successfully")
    elif choice == "3":
        success_clean = await clean_database()
        if success_clean:
            success_setup = await create_collections()
            if success_setup:
                logger.info("Database cleanup and setup completed successfully")
    elif choice == "4":
        logger.info("Exiting without changes")
    else:
        logger.error("Invalid choice")
    
    # Close connection
    await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(main())