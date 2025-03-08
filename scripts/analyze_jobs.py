#!/usr/bin/env python
# scripts/analyze_jobs.py
import asyncio
import sys
import os
from collections import Counter
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.core.logging import logger
from app.db.mongodb import mongodb
from app.db.repositories.jobs import JobsRepository

async def analyze_jobs():
    """Analyze jobs in the database."""
    # Connect to MongoDB
    connected = await mongodb.connect()
    if not connected:
        logger.error("Failed to connect to MongoDB")
        return
    
    # Initialize repository
    jobs_repository = JobsRepository()
    
    # Get all jobs
    collection = mongodb.get_collection("jobs")
    cursor = collection.find({})
    
    jobs_data = []
    async for job in cursor:
        jobs_data.append(job)
    
    logger.info(f"Analyzing {len(jobs_data)} jobs...")
    
    if not jobs_data:
        logger.info("No jobs found to analyze")
        return
    
    # Create DataFrame
    df = pd.DataFrame(jobs_data)
    
    # Analysis 1: Jobs by source
    logger.info("\nJobs by Source:")
    source_counts = df["source"].value_counts()
    for source, count in source_counts.items():
        logger.info(f"{source}: {count} jobs")
    
    # Analysis 2: Jobs by company
    logger.info("\nTop 10 Companies:")
    company_counts = df["company_name"].value_counts().head(10)
    for company, count in company_counts.items():
        logger.info(f"{company}: {count} jobs")
    
    # Analysis 3: Remote vs. On-site
    logger.info("\nRemote vs. On-site:")
    remote_counts = df["is_remote"].value_counts()
    for is_remote, count in remote_counts.items():
        status = "Remote" if is_remote else "On-site/Hybrid"
        logger.info(f"{status}: {count} jobs")
    
    # Analysis 4: Job types
    if "job_type" in df.columns:
        job_types = []
        for types in df["job_type"].dropna():
            if isinstance(types, list):
                job_types.extend(types)
        
        logger.info("\nJob Types:")
        job_type_counts = Counter(job_types)
        for job_type, count in job_type_counts.most_common():
            logger.info(f"{job_type}: {count} jobs")
    
    # Analysis 5: Jobs by date
    if "date_posted" in df.columns:
        df["date_posted"] = pd.to_datetime(df["date_posted"])
        
        # Group by date
        date_counts = df["date_posted"].dt.date.value_counts().sort_index()
        
        logger.info("\nJobs by Date Posted:")
        for date, count in date_counts.items():
            logger.info(f"{date}: {count} jobs")
    
    # Analysis 6: Salary information
    if "compensation" in df.columns:
        salaries = []
        for comp in df["compensation"].dropna():
            if isinstance(comp, dict) and "min_amount" in comp and comp["min_amount"]:
                interval = comp.get("interval", "yearly")
                min_amount = comp["min_amount"]
                
                # Normalize to yearly
                if interval == "hourly":
                    min_amount *= 2080  # 40 hours * 52 weeks
                elif interval == "daily":
                    min_amount *= 260  # 5 days * 52 weeks
                elif interval == "weekly":
                    min_amount *= 52
                elif interval == "monthly":
                    min_amount *= 12
                
                salaries.append(min_amount)
        
        if salaries:
            logger.info("\nSalary Statistics (Yearly Equivalent):")
            logger.info(f"Average: ${sum(salaries)/len(salaries):,.2f}")
            logger.info(f"Minimum: ${min(salaries):,.2f}")
            logger.info(f"Maximum: ${max(salaries):,.2f}")
            
            # Salary ranges
            salary_ranges = [
                (0, 50000),
                (50000, 75000),
                (75000, 100000),
                (100000, 125000),
                (125000, 150000),
                (150000, float('inf'))
            ]
            
            logger.info("\nSalary Distribution:")
            for min_range, max_range in salary_ranges:
                count = sum(1 for s in salaries if min_range <= s < max_range)
                if max_range == float('inf'):
                    logger.info(f"${min_range:,}+: {count} jobs")
                else:
                    logger.info(f"${min_range:,} - ${max_range:,}: {count} jobs")
    
    # Analysis 7: Most common job titles
    logger.info("\nTop 10 Job Titles:")
    title_counts = df["title"].value_counts().head(10)
    for title, count in title_counts.items():
        logger.info(f"{title}: {count} jobs")
    
    # Disconnect from MongoDB
    await mongodb.disconnect()

if __name__ == "__main__":
    # Set up configuration
    settings.DEBUG = True
    
    # Run analysis
    asyncio.run(analyze_jobs())