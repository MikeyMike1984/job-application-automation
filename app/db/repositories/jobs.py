# app/db/repositories/jobs.py
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson.objectid import ObjectId

from app.core.models import JobPost
from app.db.mongodb import mongodb

class JobsRepository:
    """Repository for job operations."""
    
    def __init__(self):
        """Initialize jobs repository."""
        self.collection_name = "jobs"
    
    def _get_collection(self):
        """Get jobs collection."""
        return mongodb.get_collection(self.collection_name)
    
    async def insert(self, job: JobPost) -> str:
        """Insert a job post.
        
        Args:
            job: Job post to insert
            
        Returns:
            ID of inserted job
        """
        collection = self._get_collection()
        job_dict = job.dict(exclude={"id"})
        result = await collection.insert_one(job_dict)
        return str(result.inserted_id)
    
    async def find_by_id(self, job_id: str) -> Optional[JobPost]:
        """Find job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            JobPost if found, None otherwise
        """
        collection = self._get_collection()
        job_data = await collection.find_one({"_id": ObjectId(job_id)})
        
        if not job_data:
            return None
            
        # Convert _id to string ID
        job_data["id"] = str(job_data.pop("_id"))
        return JobPost(**job_data)
    
    async def update(self, job_id: str, update_data: Dict[str, Any]) -> bool:
        """Update job.
        
        Args:
            job_id: Job ID
            update_data: Data to update
            
        Returns:
            True if update successful, False otherwise
        """
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def find_by_status(self, status: str, limit: int = 100) -> List[JobPost]:
        """Find jobs by status.
        
        Args:
            status: Status to filter by
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs
        """
        collection = self._get_collection()
        cursor = collection.find({"status": status}).limit(limit)
        jobs = []
        
        async for job_data in cursor:
            job_data["id"] = str(job_data.pop("_id"))
            jobs.append(JobPost(**job_data))
            
        return jobs
    
    async def find_by_company(self, company_name: str) -> List[JobPost]:
        """Find jobs by company name.
        
        Args:
            company_name: Company name to filter by
            
        Returns:
            List of jobs
        """
        collection = self._get_collection()
        cursor = collection.find({"company_name": {"$regex": company_name, "$options": "i"}})
        jobs = []
        
        async for job_data in cursor:
            job_data["id"] = str(job_data.pop("_id"))
            jobs.append(JobPost(**job_data))
            
        return jobs