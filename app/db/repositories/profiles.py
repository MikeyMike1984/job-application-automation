# app/db/repositories/profiles.py
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson.objectid import ObjectId

from app.core.models import UserProfile
from app.db.mongodb import mongodb

class ProfilesRepository:
    """Repository for user profile operations."""
    
    def __init__(self):
        """Initialize profiles repository."""
        self.collection_name = "profiles"
    
    def _get_collection(self):
        """Get profiles collection."""
        return mongodb.get_collection(self.collection_name)
    
    async def insert(self, profile: UserProfile) -> str:
        """Insert a user profile.
        
        Args:
            profile: User profile to insert
            
        Returns:
            ID of inserted profile
        """
        collection = self._get_collection()
        profile_dict = profile.dict(exclude={"id"})
        result = await collection.insert_one(profile_dict)
        return str(result.inserted_id)
    
    async def find_by_id(self, profile_id: str) -> Optional[UserProfile]:
        """Find profile by ID.
        
        Args:
            profile_id: Profile ID
            
        Returns:
            UserProfile if found, None otherwise
        """
        collection = self._get_collection()
        profile_data = await collection.find_one({"_id": ObjectId(profile_id)})
        
        if not profile_data:
            return None
            
        # Convert _id to string ID
        profile_data["id"] = str(profile_data.pop("_id"))
        return UserProfile(**profile_data)
    
    async def find_by_email(self, email: str) -> Optional[UserProfile]:
        """Find profile by email.
        
        Args:
            email: User email
            
        Returns:
            UserProfile if found, None otherwise
        """
        collection = self._get_collection()
        profile_data = await collection.find_one({"contact.email": email})
        
        if not profile_data:
            return None
            
        # Convert _id to string ID
        profile_data["id"] = str(profile_data.pop("_id"))
        return UserProfile(**profile_data)
    
    async def update(self, profile_id: str, update_data: Dict[str, Any]) -> bool:
        """Update profile.
        
        Args:
            profile_id: Profile ID
            update_data: Data to update
            
        Returns:
            True if update successful, False otherwise
        """
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await collection.update_one(
            {"_id": ObjectId(profile_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def find_all(self) -> List[UserProfile]:
        """Find all profiles.
        
        Returns:
            List of all user profiles
        """
        collection = self._get_collection()
        cursor = collection.find()
        profiles = []
        
        async for profile_data in cursor:
            profile_data["id"] = str(profile_data.pop("_id"))
            profiles.append(UserProfile(**profile_data))
            
        return profiles
    
    async def add_skill(self, profile_id: str, skill: Dict[str, Any]) -> bool:
        """Add a skill to a profile.
        
        Args:
            profile_id: Profile ID
            skill: Skill data
            
        Returns:
            True if add successful, False otherwise
        """
        collection = self._get_collection()
        
        result = await collection.update_one(
            {"_id": ObjectId(profile_id)},
            {
                "$push": {"skills": skill},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    async def add_experience(self, profile_id: str, experience: Dict[str, Any]) -> bool:
        """Add an experience to a profile.
        
        Args:
            profile_id: Profile ID
            experience: Experience data
            
        Returns:
            True if add successful, False otherwise
        """
        collection = self._get_collection()
        
        result = await collection.update_one(
            {"_id": ObjectId(profile_id)},
            {
                "$push": {"experiences": experience},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    async def update_contact_info(self, profile_id: str, contact_info: Dict[str, Any]) -> bool:
        """Update contact information.
        
        Args:
            profile_id: Profile ID
            contact_info: Contact information
            
        Returns:
            True if update successful, False otherwise
        """
        collection = self._get_collection()
        
        result = await collection.update_one(
            {"_id": ObjectId(profile_id)},
            {
                "$set": {
                    "contact": contact_info,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0