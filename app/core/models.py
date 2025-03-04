# app/core/models.py
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class JobType(str, Enum):
    """Job types enumeration."""
    FULL_TIME = "fulltime"
    PART_TIME = "parttime"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"


class CompensationInterval(str, Enum):
    """Compensation interval enumeration."""
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly" 
    DAILY = "daily"
    HOURLY = "hourly"


class Location(BaseModel):
    """Location model."""
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    
    def display_location(self) -> str:
        """Format location as a string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


class Compensation(BaseModel):
    """Compensation model."""
    interval: Optional[CompensationInterval] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: str = "USD"


class JobPost(BaseModel):
    """Job posting model."""
    id: Optional[str] = None
    source: str
    title: str
    company_name: str
    location: Optional[Location] = None
    job_url: str
    job_url_direct: Optional[str] = None
    description: Optional[str] = None
    job_type: Optional[List[JobType]] = None
    compensation: Optional[Compensation] = None
    date_posted: Optional[datetime] = None
    date_scraped: datetime = Field(default_factory=datetime.utcnow)
    is_remote: Optional[bool] = None
    emails: Optional[List[str]] = None
    status: str = "new"
    analysis: Optional[Dict[str, Any]] = None


class ProfileSkill(BaseModel):
    """Professional skill model."""
    name: str
    years: Optional[int] = None
    level: Optional[str] = None
    description: Optional[str] = None


class ProfileExperience(BaseModel):
    """Professional experience model."""
    company: str
    title: str
    start_date: str
    end_date: Optional[str] = None
    description: Optional[str] = None
    achievements: List[str] = []
    skills_used: List[str] = []
    location: Optional[str] = None


class ProfileEducation(BaseModel):
    """Education model."""
    degree: str
    field: str
    institution: str
    location: Optional[str] = None
    graduation_date: Optional[str] = None
    achievements: List[str] = []


class ProfileCertification(BaseModel):
    """Certification model."""
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    expiration_date: Optional[str] = None
    url: Optional[str] = None


class UserContactInfo(BaseModel):
    """User contact information."""
    email: str
    phone: str
    linkedin: Optional[str] = None
    website: Optional[str] = None
    location: Location


class UserProfile(BaseModel):
    """User professional profile."""
    id: Optional[str] = None
    name: Dict[str, str]  # {"first": "...", "last": "..."}
    title: str
    contact: UserContactInfo
    summary: Optional[str] = None
    skills: List[ProfileSkill] = []
    experiences: List[ProfileExperience] = []
    education: List[ProfileEducation] = []
    certifications: List[ProfileCertification] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeDocument(BaseModel):
    """Resume document model."""
    id: Optional[str] = None
    user_id: str
    job_id: Optional[str] = None
    file_path: str
    file_name: str
    file_format: str
    customization: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class ApplicationStatus(str, Enum):
    """Application status enumeration."""
    NEW = "new"
    RESUME_GENERATED = "resume_generated"
    APPLYING = "applying"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobApplication(BaseModel):
    """Job application model."""
    id: Optional[str] = None
    job_id: str
    user_id: str
    resume_id: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.NEW
    applied_at: Optional[datetime] = None
    application_url: Optional[str] = None
    questions_answered: Optional[Dict[str, str]] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)