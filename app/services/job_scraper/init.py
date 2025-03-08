# app/services/job_scraper/__init__.py
from app.services.job_scraper.base import BaseScraper
from app.services.job_scraper.linkedin import LinkedInScraper
from app.services.job_scraper.indeed import IndeedScraper
from app.services.job_scraper.service import ScraperService

__all__ = [
    'BaseScraper',
    'LinkedInScraper',
    'IndeedScraper',
    'ScraperService'
]