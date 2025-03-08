# app/services/job_scraper/service.py
import asyncio
from typing import List, Dict, Any, Optional, Type, Union
import logging

from app.core.models import JobPost, JobType
from app.services.job_scraper.base import BaseScraper
from app.services.job_scraper.linkedin import LinkedInScraper
from app.services.job_scraper.indeed import IndeedScraper
from app.core.exceptions import ScraperError
from app.db.repositories.jobs import JobsRepository
from app.config import settings

logger = logging.getLogger(__name__)

class ScraperService:
    """Service for coordinating job scraping across platforms."""
    
    SCRAPERS = {
        "linkedin": LinkedInScraper,
        "indeed": IndeedScraper,
    }
    
    def __init__(self, jobs_repository: JobsRepository):
        """Initialize scraper service.
        
        Args:
            jobs_repository: Repository for job storage
        """
        self.jobs_repository = jobs_repository
        self.scrapers = {}
    
    def get_scraper(self, platform: str) -> BaseScraper:
        """Get or create a scraper for the specified platform.
        
        Args:
            platform: Platform name (e.g., "linkedin", "indeed")
            
        Returns:
            Scraper instance
            
        Raises:
            ValueError: If platform is not supported
        """
        if platform not in self.SCRAPERS:
            raise ValueError(f"Unsupported platform: {platform}")
        
        if platform not in self.scrapers:
            scraper_class = self.SCRAPERS[platform]
            self.scrapers[platform] = scraper_class(
                proxies=settings.SCRAPER.PROXIES if settings.SCRAPER.USE_PROXIES else None
            )
        
        return self.scrapers[platform]
    
    async def search_jobs(self, 
                   platforms: List[str],
                   search_term: str,
                   location: Optional[str] = None,
                   job_type: Optional[Union[JobType, str]] = None,
                   max_results_per_platform: int = 20,
                   remote_only: bool = False,
                   store_results: bool = True,
                   **kwargs) -> List[JobPost]:
        """Search for jobs across multiple platforms.
        
        Args:
            platforms: List of platform names to search
            search_term: Job search keyword
            location: Location to search in
            job_type: Type of job
            max_results_per_platform: Maximum results per platform
            remote_only: Filter for remote jobs only
            store_results: Whether to store results in database
            **kwargs: Additional platform-specific parameters
            
        Returns:
            List of job postings
        """
        # Convert job_type to enum if it's a string
        if isinstance(job_type, str):
            try:
                job_type = JobType(job_type)
            except ValueError:
                logger.warning(f"Invalid job type: {job_type}")
                job_type = None
        
        # Create tasks for each platform
        tasks = []
        for platform in platforms:
            try:
                scraper = self.get_scraper(platform)
                tasks.append(
                    scraper.search_jobs(
                        search_term=search_term,
                        location=location,
                        job_type=job_type,
                        max_results=max_results_per_platform,
                        remote_only=remote_only,
                        **kwargs
                    )
                )
            except ValueError as e:
                logger.error(str(e))
        
        # Run tasks concurrently
        all_jobs = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error scraping {platforms[i]}: {str(result)}")
                else:
                    all_jobs.extend(result)
                    
                    # Store results if requested
                    if store_results:
                        for job in result:
                            try:
                                # Check if job already exists by ID or URL
                                # (This would require an additional repository method)
                                await self.jobs_repository.insert(job)
                            except Exception as e:
                                logger.error(f"Error storing job {job.id}: {str(e)}")
        
        return all_jobs
    
    async def get_job_details(self, platform: str, job_url: str) -> Dict[str, Any]:
        """Get detailed job information from specified platform.
        
        Args:
            platform: Platform name
            job_url: URL or ID of job
            
        Returns:
            Detailed job information
            
        Raises:
            ValueError: If platform is not supported
            ScraperError: If scraping fails
        """
        scraper = self.get_scraper(platform)
        return await scraper.get_job_details(job_url)
    
    async def close(self):
        """Close all scraper sessions."""
        for scraper in self.scrapers.values():
            await scraper.close_session()