#!/usr/bin/env python
# scripts/test_job_scraper.py
import asyncio
import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.core.logging import logger
from app.db.mongodb import mongodb
from app.db.repositories.jobs import JobsRepository
from app.services.job_scraper import LinkedInScraper, IndeedScraper, ScraperService
from app.core.models import JobPost

async def test_mongodb_connection():
    """Test MongoDB connection."""
    logger.info("Testing MongoDB connection...")
    
    connected = await mongodb.connect()
    if connected:
        logger.info("Successfully connected to MongoDB!")
        
        # Verify collection access
        collection = mongodb.get_collection("test_collection")
        test_doc = {"test": True, "timestamp": datetime.utcnow()}
        await collection.insert_one(test_doc)
        logger.info("Successfully inserted test document!")
        
        result = await collection.find_one({"test": True})
        logger.info(f"Successfully retrieved test document: {result}")
        
        await collection.delete_many({"test": True})
        logger.info("Successfully cleaned up test documents!")
        
        return True
    else:
        logger.error("Failed to connect to MongoDB!")
        return False

async def test_job_scraper(platform: str, search_term: str, location: str, max_results: int = 5):
    """Test job scraper for a specific platform."""
    logger.info(f"Testing {platform} job scraper...")
    
    try:
        if platform.lower() == "linkedin":
            scraper = LinkedInScraper()
        elif platform.lower() == "indeed":
            scraper = IndeedScraper()
        else:
            logger.error(f"Unsupported platform: {platform}")
            return None
        
        await scraper.setup_session()
        
        jobs = await scraper.search_jobs(
            search_term=search_term,
            location=location,
            max_results=max_results
        )
        
        logger.info(f"Successfully found {len(jobs)} jobs on {platform}")
        
        # Print summary of each job
        for i, job in enumerate(jobs, 1):
            job_location = job.location.display_location() if job.location else "N/A"
            logger.info(f"Job {i}: {job.title} at {job.company_name} in {job_location}")
        
        # Get details for the first job if available
        if jobs:
            logger.info(f"Getting detailed information for first job...")
            job_details = await scraper.get_job_details(jobs[0].job_url)
            logger.info(f"Successfully retrieved job details with {len(job_details)} fields")
        
        await scraper.close_session()
        return jobs
    
    except Exception as e:
        logger.error(f"Error testing {platform} scraper: {str(e)}")
        return None

async def test_scraper_service(search_term: str, location: str, max_results: int = 5):
    """Test the scraper service with multiple platforms."""
    logger.info("Testing ScraperService...")
    
    try:
        # Initialize repositories
        jobs_repository = JobsRepository()
        
        # Initialize service
        service = ScraperService(jobs_repository)
        
        # Test searching across platforms
        platforms = ["linkedin", "indeed"]
        jobs = await service.search_jobs(
            platforms=platforms,
            search_term=search_term,
            location=location,
            max_results_per_platform=max_results,
            store_results=True
        )
        
        logger.info(f"Successfully found {len(jobs)} jobs across {len(platforms)} platforms")
        
        # Count jobs per platform
        platform_counts = {}
        for job in jobs:
            platform_counts[job.source] = platform_counts.get(job.source, 0) + 1
        
        for platform, count in platform_counts.items():
            logger.info(f"Found {count} jobs from {platform}")
        
        # Close service
        await service.close()
        
        return jobs
    
    except Exception as e:
        logger.error(f"Error testing ScraperService: {str(e)}")
        return None

async def test_job_repository(jobs: List[JobPost]):
    """Test job repository for storing and retrieving jobs."""
    logger.info("Testing JobsRepository...")
    
    try:
        jobs_repository = JobsRepository()
        
        # Store jobs in database
        for job in jobs:
            job_id = await jobs_repository.insert(job)
            logger.info(f"Stored job {job.title} with ID {job_id}")
        
        # Retrieve jobs by status
        stored_jobs = await jobs_repository.find_by_status("new")
        logger.info(f"Retrieved {len(stored_jobs)} jobs with 'new' status")
        
        # Retrieve jobs by company
        if jobs:
            company_name = jobs[0].company_name
            company_jobs = await jobs_repository.find_by_company(company_name)
            logger.info(f"Retrieved {len(company_jobs)} jobs from company '{company_name}'")
            
            # Update first job
            if company_jobs:
                job_id = company_jobs[0].id
                update_success = await jobs_repository.update(
                    job_id, 
                    {"status": "processing", "updated_at": datetime.utcnow()}
                )
                logger.info(f"Updated job {job_id} status to 'processing': {update_success}")
                
                # Retrieve updated job
                updated_job = await jobs_repository.find_by_id(job_id)
                logger.info(f"Retrieved updated job: {updated_job.title} with status {updated_job.status}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing JobsRepository: {str(e)}")
        return False

async def display_job_details(job: JobPost):
    """Display detailed information about a job."""
    logger.info("\n" + "=" * 50)
    logger.info(f"JOB DETAILS: {job.title}")
    logger.info("=" * 50)
    
    logger.info(f"ID: {job.id}")
    logger.info(f"Source: {job.source}")
    logger.info(f"Company: {job.company_name}")
    logger.info(f"Location: {job.location.display_location() if job.location else 'N/A'}")
    logger.info(f"Job Type: {', '.join(jt.value for jt in job.job_type) if job.job_type else 'N/A'}")
    logger.info(f"Remote: {'Yes' if job.is_remote else 'No'}")
    
    if job.compensation:
        interval = job.compensation.interval
        min_amount = job.compensation.min_amount
        max_amount = job.compensation.max_amount
        currency = job.compensation.currency
        
        salary_text = f"{currency} "
        if min_amount and max_amount:
            salary_text += f"{min_amount:,.2f} - {max_amount:,.2f}"
        elif min_amount:
            salary_text += f"{min_amount:,.2f}+"
        elif max_amount:
            salary_text += f"Up to {max_amount:,.2f}"
        
        if interval:
            salary_text += f" per {interval}"
        
        logger.info(f"Compensation: {salary_text}")
    else:
        logger.info("Compensation: Not specified")
    
    logger.info(f"Date Posted: {job.date_posted}")
    logger.info(f"Date Scraped: {job.date_scraped}")
    logger.info(f"Job URL: {job.job_url}")
    
    if job.job_url_direct:
        logger.info(f"Direct URL: {job.job_url_direct}")
    
    if job.emails:
        logger.info(f"Emails: {', '.join(job.emails)}")
    
    if job.description:
        desc_preview = job.description[:300] + "..." if len(job.description) > 300 else job.description
        logger.info(f"\nDescription Preview:\n{desc_preview}")
    
    logger.info("=" * 50 + "\n")

async def run_tests():
    """Run all tests."""
    # Test MongoDB connection
    db_connected = await test_mongodb_connection()
    if not db_connected:
        logger.error("MongoDB connection test failed. Exiting.")
        return
    
    # Define search parameters
    search_term = "software engineer"
    location = "New York"
    max_results = 5
    
    # Test LinkedIn scraper
    linkedin_jobs = await test_job_scraper("linkedin", search_term, location, max_results)
    
    # Test Indeed scraper
    indeed_jobs = await test_job_scraper("indeed", search_term, location, max_results)
    
    # Test ScraperService
    service_jobs = await test_scraper_service(search_term, location, max_results)
    
    # Test JobsRepository if jobs were found
    all_jobs = []
    if linkedin_jobs:
        all_jobs.extend(linkedin_jobs)
    if indeed_jobs:
        all_jobs.extend(indeed_jobs)
    
    if all_jobs:
        await test_job_repository(all_jobs)
        
        # Display detailed information for first job
        if all_jobs:
            await display_job_details(all_jobs[0])
    
    logger.info("All tests completed!")

if __name__ == "__main__":
    # Set up configuration
    settings.DEBUG = True
    
    # Run tests
    asyncio.run(run_tests())