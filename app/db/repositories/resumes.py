# app/db/repositories/resumes.py
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson.objectid import ObjectId

from app.core.models import ResumeDocument
from app.db.mongodb import mongodb

class ResumesRepository:
    """Repository for resume operations."""
    
    def __init__(self):
        """Initialize resumes repository."""
        self.collection_name = "resumes"
    
    def _get_collection(self):
        """Get resumes collection."""
        return mongodb.get_collection(self.collection_name)
    
    async def insert(self, resume: ResumeDocument) -> str:
        """Insert a resume document.
        
        Args:
            resume: Resume document to insert
            
        Returns:
            ID of inserted resume
        """
        collection = self._get_collection()
        resume_dict = resume.dict(exclude={"id"})
        result = await collection.insert_one(resume_dict)
        return str(result.inserted_id)
    
    async def find_by_id(self, resume_id: str) -> Optional[ResumeDocument]:
        """Find resume by ID.
        
        Args:
            resume_id: Resume ID
            
        Returns:
            ResumeDocument if found, None otherwise
        """
        collection = self._get_collection()
        resume_data = await collection.find_one({"_id": ObjectId(resume_id)})
        
        if not resume_data:
            return None
            
        # Convert _id to string ID
        resume_data["id"] = str(resume_data.pop("_id"))
        return ResumeDocument(**resume_data)
    
    async def find_by_user(self, user_id: str) -> List[ResumeDocument]:
        """Find resumes by user ID.
        
        Args:
            user_id: User ID
            
        Returns:
            List of resumes
        """
        collection = self._get_collection()
        cursor = collection.find({"user_id": user_id})
        resumes = []
        
        async for resume_data in cursor:
            resume_data["id"] = str(resume_data.pop("_id"))
            resumes.append(ResumeDocument(**resume_data))
            
        return resumes
    
    async def find_by_job(self, job_id: str) -> List[ResumeDocument]:
        """Find resumes by job ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of resumes
        """
        collection = self._get_collection()
        cursor = collection.find({"job_id": job_id})
        resumes = []
        
        async for resume_data in cursor:
            resume_data["id"] = str(resume_data.pop("_id"))
            resumes.append(ResumeDocument(**resume_data))
            
        return resumes
    
    async def update(self, resume_id: str, update_data: Dict[str, Any]) -> bool:
        """Update resume.
        
        Args:
            resume_id: Resume ID
            update_data: Data to update
            
        Returns:
            True if update successful, False otherwise
        """
        collection = self._get_collection()
        
        result = await collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def delete(self, resume_id: str) -> bool:
        """Delete resume.
        
        Args:
            resume_id: Resume ID
            
        Returns:
            True if deletion successful, False otherwise
        """
        collection = self._get_collection()
        
        result = await collection.delete_one({"_id": ObjectId(resume_id)})
        
        return result.deleted_count > 0
    
    async def find_latest_by_user_and_job(self, user_id: str, job_id: str) -> Optional[ResumeDocument]:
        """Find latest resume for a user and job.
        
        Args:
            user_id: User ID
            job_id: Job ID
            
        Returns:
            Latest ResumeDocument if found, None otherwise
        """
        collection = self._get_collection()
        resume_data = await collection.find_one(
            {"user_id": user_id, "job_id": job_id},
            sort=[("created_at", -1)]
        )
        
        if not resume_data:
            return None
            
        # Convert _id to string ID
        resume_data["id"] = str(resume_data.pop("_id"))
        return ResumeDocument(**resume_data)