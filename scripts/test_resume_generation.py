# scripts/test_resume_generation.py

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.core.logging import logger
from app.db.mongodb import mongodb
from app.core.models import UserProfile, JobPost, Location, Compensation, CompensationInterval, JobType
from app.services.resume_builder.analyzer import JobAnalyzer
from app.services.resume_builder.matcher import ProfileMatcher
from app.services.resume_builder.generator import ResumeGenerator

async def create_test_profile():
    """Create a test user profile."""
    profile = UserProfile(
        name={"first": "Michael", "last": "Reeves"},
        title="Senior Operations Manager",
        contact={
            "email": "mreeves30.IE@gmail.com",
            "phone": "817-908-9168",
            "linkedin": "www.linkedin.com/in/michael-reeves-1a2b3c/",
            "website": None,
            "location": Location(city="Fort Worth", state="TX", country="USA")
        },
        summary="Results-driven Senior Operations Leader with over 10 years of experience managing high-volume manufacturing and distribution operations. Proven expertise in Lean techniques, team development, and implementing quality and process improvements. Skilled in driving operational excellence, optimizing fulfillment center performance, and building strong cross-functional collaboration to achieve business goals.",
        skills=[
            {"name": "Operations Management", "years": 10, "level": "Expert", "description": "Fulfillment center operations, inventory control, staffing lifecycle, KPI-driven performance, multi-site management."},
            {"name": "Leadership & Development", "years": 8, "level": "Expert", "description": "Team leadership, coaching and mentoring, cross-functional collaboration, leadership bench strength."},
            {"name": "Process Improvement", "years": 7, "level": "Advanced", "description": "Lean Manufacturing, Six Sigma principles, continuous improvement, process change initiatives."},
            {"name": "Technical Skills", "years": 5, "level": "Advanced", "description": "SQL, Power BI, VBA, Python, ERP systems integration, advanced Excel, data-driven decision-making."},
            {"name": "Strategic Execution", "years": 6, "level": "Advanced", "description": "Strategic planning, forecasting, budget management, cost optimization, quality and safety compliance."}
        ],
        experiences=[
            {
                "company": "GRAero Co.",
                "title": "Aerospace Systems Consultant",
                "start_date": "2024-04",
                "end_date": "2024-10",
                "description": "Led cross-functional teams to optimize communication between engineering and ground staff, improving operational efficiency and reducing downtime.",
                "achievements": [
                    "Led cross-functional teams to optimize communication between engineering and ground staff.",
                    "Drove process improvements utilizing Lean Manufacturing and Six Sigma principles."
                ],
                "skills_used": ["Lean Manufacturing", "Process Improvement", "Leadership", "Cross-functional Collaboration"],
                "location": "Dallas, TX"
            },
            {
                "company": "Hillwood Properties",
                "title": "Business Process Consultant",
                "start_date": "2023-06",
                "end_date": "2024-01",
                "description": "Led cross-functional teams to define quarterly demand for consumables, negotiating vendor pricing and achieving a 54% ($294,840) reduction in yearly expenditures.",
                "achievements": [
                    "Led cross-functional teams to define quarterly demand for consumables, achieving a 54% ($294,840) reduction in yearly expenditures.",
                    "Redesigned and optimized maintenance workshops across multiple sites, implementing 5S, visual management techniques, and FIFO processes."
                ],
                "skills_used": ["Process Improvement", "Cost Optimization", "Lean Techniques", "FIFO", "5S"],
                "location": "Fort Worth, TX"
            },
            {
                "company": "Marley Spoon",
                "title": "National Warehouse Operations Manager",
                "start_date": "2020-12",
                "end_date": "2022-12",
                "description": "Directed inventory teams across three U.S. facilities (NJ, TX, CA), overseeing 2 Shift Managers, 5 Team Leads, and 40-80 associates at each site.",
                "achievements": [
                    "Conducted foundational time studies to develop realistic labor metrics for 20+ job functions.",
                    "Partnered with finance and operations leadership to establish, staff, and train ICQA departments, achieving a 17% improvement in inventory accuracy.",
                    "Designed and executed enhanced cycle counting strategies, reconciling virtual and physical inventory.",
                    "Championed the implementation of ERP systems, serving as NAV SME for the U.S."
                ],
                "skills_used": ["Multi-site Management", "ERP Implementation", "Inventory Control", "Labor Planning", "Team Leadership"],
                "location": "Dallas, TX"
            }
        ],
        education=[
            {
                "degree": "Bachelor of Science",
                "field": "Industrial Engineering",
                "institution": "The University of Texas",
                "location": "Arlington, TX",
                "graduation_date": "2015"
            }
        ],
        certifications=[
            {
                "name": "Lean Green Belt Certification",
                "issuer": "Institute of Industrial Engineers",
                "date": "2015-04"
            },
            {
                "name": "Lean Six Sigma Yellow Belt Certification",
                "issuer": "Bell Helicopter",
                "date": "2014-04"
            },
            {
                "name": "Certified AutoCAD Technician",
                "issuer": None,
                "date": None
            }
        ]
    )
    return profile

async def create_test_job():
    """Create a test job posting."""
    job = JobPost(
        id="test-job-001",
        source="linkedin",
        title="Operations Manager - Fulfillment Center",
        company_name="E-Commerce Solutions Inc.",
        location=Location(city="Dallas", state="TX", country="USA"),
        job_url="https://example.com/jobs/operations-manager",
        job_url_direct=None,
        description="""
        We are seeking an experienced Operations Manager to lead our growing fulfillment center operations in Dallas, TX.
        
        Responsibilities:
        • Oversee day-to-day operations of our fulfillment center, including receiving, inventory management, and shipping
        • Manage a team of 50+ associates across multiple shifts, developing talent and ensuring high performance
        • Implement Lean methodologies to improve process efficiency and reduce operational costs
        • Drive continuous improvement initiatives focused on quality, safety, and productivity
        • Collaborate with cross-functional teams (Planning, HR, IT) to streamline operations
        • Monitor and analyze key performance metrics to identify improvement opportunities
        • Ensure compliance with safety standards and regulations
        
        Requirements:
        • 5+ years of experience in operations management, preferably in e-commerce or distribution
        • Proven track record of implementing Lean and Six Sigma methodologies
        • Strong leadership skills with experience managing large teams
        • Experience with ERP systems and inventory management
        • Knowledge of warehouse operations and logistics best practices
        • Excellent analytical skills and proficiency with data analysis tools (Excel, Power BI)
        • Bachelor's degree in Supply Chain, Operations, Industrial Engineering, or related field
        
        Preferred Skills:
        • Experience with Microsoft NAV or similar ERP systems
        • Knowledge of warehouse management systems (WMS)
        • Experience with process improvement methodologies
        • Strong SQL skills for data analysis
        
        This position offers competitive compensation and benefits, including healthcare, 401k matching, and career advancement opportunities.
        """,
        job_type=[JobType.FULL_TIME],
        compensation=Compensation(
            interval=CompensationInterval.YEARLY,
            min_amount=85000,
            max_amount=110000,
            currency="USD"
        ),
        date_posted=datetime.now().date(),
        date_scraped=datetime.now(),
        is_remote=False,
        emails=["careers@ecommercesolutions.example.com"],
        status="new"
    )
    return job

async def test_resume_generation():
    """Test the resume generation pipeline."""
    # Connect to MongoDB
    connected = await mongodb.connect()
    if not connected:
        logger.error("Failed to connect to MongoDB")
        return
    
    try:
        # Create test data
        profile = await create_test_profile()
        job = await create_test_job()
        
        # Set up resume generation components
        analyzer = JobAnalyzer()
        matcher = ProfileMatcher(analyzer)
        generator = ResumeGenerator(job_analyzer=analyzer, profile_matcher=matcher)
        
        # Step 1: Analyze job
        logger.info("Analyzing job...")
        job_analysis = await analyzer.analyze_job(job)
        job.analysis = job_analysis
        
        logger.info(f"Job analysis complete. Extracted {len(job_analysis.get('skills', []))} skills.")
        
        # Step 2: Match profile to job
        logger.info("Matching profile to job...")
        match_results = await matcher.match_profile_to_job(profile, job)
        
        logger.info(f"Match results: {match_results['overall_match']}% overall match ({match_results['fit_category']} fit)")
        logger.info(f"Skill match: {match_results['skill_match']['score']}%")
        logger.info(f"Experience match: {match_results['experience_match']['score'] * 100}%")
        logger.info(f"Education match: {match_results['education_match']['score'] * 100}%")
        
        # Step 3: Generate resume
        logger.info("Generating tailored resume...")
        resume_doc = await generator.generate_resume(profile, job)
        
        logger.info(f"Resume generated successfully: {resume_doc.file_path}")
        logger.info(f"Overall match score: {resume_doc.customization['match_score']}%")
        logger.info(f"Top skills highlighted: {', '.join(resume_doc.customization['highlighted_skills'])}")
        
        # Success!
        logger.info("Resume generation pipeline test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during resume generation test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Disconnect from MongoDB
    await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(test_resume_generation())