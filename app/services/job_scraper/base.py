# app/services/job_scraper/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.models import JobPost, Location, JobType, Compensation
from app.config import settings
from app.core.logging import logger
from app.core.exceptions import ScraperError

class BaseScraper(ABC):
    """Base class for job scrapers."""
    
    def __init__(self, proxies: Optional[List[str]] = None):
        """Initialize base scraper.
        
        Args:
            proxies: List of proxy URLs to use for requests.
        """
        self.proxies = proxies or settings.SCRAPER.PROXIES
        self.use_proxies = settings.SCRAPER.USE_PROXIES and bool(self.proxies)
        self.retry_count = settings.SCRAPER.RETRY_COUNT
        self.retry_delay = settings.SCRAPER.RETRY_DELAY
        self.timeout = settings.SCRAPER.REQUEST_TIMEOUT
        self.user_agent = settings.SCRAPER.USER_AGENT
        self.session = None
        
    @abstractmethod
    async def search_jobs(self, 
                    search_term: str, 
                    location: Optional[str] = None,
                    job_type: Optional[JobType] = None,
                    max_results: int = 20,
                    remote_only: bool = False,
                    **kwargs) -> List[JobPost]:
        """Search for jobs using provided criteria.
        
        Args:
            search_term: Job search keyword
            location: Location to search in
            job_type: Type of job (full-time, part-time, etc.)
            max_results: Maximum number of results to return
            remote_only: Filter for remote jobs only
            **kwargs: Additional platform-specific parameters
            
        Returns:
            List of job postings
            
        Raises:
            ScraperError: If an error occurs during scraping
        """
        pass
    
    @abstractmethod
    async def get_job_details(self, job_url: str) -> Dict[str, Any]:
        """Get detailed information about a job.
        
        Args:
            job_url: URL of the job posting
            
        Returns:
            Dictionary with detailed job information
            
        Raises:
            ScraperError: If an error occurs during scraping
        """
        pass
    
    @abstractmethod
    async def setup_session(self):
        """Set up HTTP session for requests.
        
        Raises:
            ScraperError: If unable to set up session
        """
        pass
    
    async def close_session(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    @staticmethod
    def normalize_job_data(job_data: Dict[str, Any], source: str) -> JobPost:
        """Normalize job data into a standard JobPost object.
        
        Args:
            job_data: Platform-specific job data
            source: Source platform name
            
        Returns:
            Normalized JobPost object
        """
        # Default values
        job_id = job_data.get('id', None)
        job_url = job_data.get('job_url', '')
        
        # Create location object if location data exists
        location = None
        location_data = job_data.get('location', {})
        if isinstance(location_data, dict) and any(location_data.values()):
            location = Location(**location_data)
        
        # Create compensation object if salary data exists
        compensation = None
        compensation_data = job_data.get('compensation', {})
        if isinstance(compensation_data, dict) and any(compensation_data.values()):
            compensation = Compensation(**compensation_data)
        
        # Format job types
        job_types = job_data.get('job_type', [])
        formatted_job_types = []
        for jt in job_types:
            if isinstance(jt, str):
                try:
                    formatted_job_types.append(JobType(jt))
                except ValueError:
                    logger.warning(f"Unknown job type: {jt}")
            elif isinstance(jt, JobType):
                formatted_job_types.append(jt)
        
        # Parse date posted if string
        date_posted = job_data.get('date_posted')
        if isinstance(date_posted, str):
            try:
                date_posted = datetime.fromisoformat(date_posted)
            except ValueError:
                logger.warning(f"Unable to parse date: {date_posted}")
                date_posted = None
        
        # Construct normalized JobPost
        return JobPost(
            id=job_id,
            source=source,
            title=job_data.get('title', ''),
            company_name=job_data.get('company_name', ''),
            location=location,
            job_url=job_url,
            job_url_direct=job_data.get('job_url_direct'),
            description=job_data.get('description'),
            job_type=formatted_job_types if formatted_job_types else None,
            compensation=compensation,
            date_posted=date_posted,
            date_scraped=datetime.utcnow(),
            is_remote=job_data.get('is_remote', False),
            emails=job_data.get('emails'),
            status="new"
        )