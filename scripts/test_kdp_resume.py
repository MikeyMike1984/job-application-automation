# scripts/test_kdp_resume.py

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
from app.services.llm.provider_simple import OllamaProvider, LLMProviderFactory

async def create_test_profile():
    """Create a test user profile using Michael Reeves' data."""
    # Using the same profile as before
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
            {"name": "Strategic Execution", "years": 6, "level": "Advanced", "description": "Strategic planning, forecasting, budget management, cost optimization, quality and safety compliance."},
            {"name": "Project Management", "years": 7, "level": "Advanced", "description": "End-to-end project lifecycle, milestone tracking, cross-functional team leadership, resource allocation."},
            {"name": "Supply Chain Management", "years": 5, "level": "Advanced", "description": "Inventory management, logistics, demand planning, supplier relationships, ERP systems."}
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

async def create_kdp_job():
    """Create a job posting for the KDP Sr Program Manager position."""
    job = JobPost(
        id="kdp-106677",
        source="company_website",
        title="Sr Program Manager, Supply Chain Strategic Program Execution",
        company_name="Keurig Dr Pepper",
        location=Location(city="Frisco", state="TX", country="USA"),
        job_url="https://careers.keurigdrpepper.com/jobs/106677",
        job_url_direct=None,
        description="""
Job Overview:
The Sr Program Manager, Supply Chain Strategic Program Execution will have two major job responsibilities:

End-to-End Program (E2E) Management

Will be the E2E program manager for assigned KDP New, Unique, Difficult, or BU required projects with accountability to deliver these projects OTIF. This role will be responsible for managing the entire lifecycle of projects, from planning and execution to monitoring performance and refining strategies to meet KPIs.
Utilize strong project management skills with the ability to handle multiple projects simultaneously while maintaining attention to detail
Define performance criteria, develop timelines, estimate capital budgets, and manage project spend for each assigned project
Make methodical, fact-based decisions derived from data which are critical to the success of each project
Work closely with cross-functional partners to execute high-impact initiatives, ensuring alignment and timely delivery. Build strategic relationships with internal and external partners to ensure continued alignment and success - before, during, and post project implementation
Must be a strategic thinker with excellent leadership and communication skills, capable of driving project success and ensuring alignment with business objectives
Serve as a resource to BUs in the planning and execution of projects and programs

Continuous Improvement

Share the responsibility for developing, maintaining, and improving program and project management methods and tools that can be used across the Supply Chain organization
Drive lean and standard work principles to ensure early, cross-functional alignment. Identify, develop, and execute cost savings programs in each project to support business productivity metrics
Playbook creation for strategic projects that can be used as references for the Supply Chain organization
Conduct regular project reviews and post-project evaluations to capture lessons learned and drive process improvements
Regularly assess project outcomes, identify opportunities for scaling and improving processes, and report on key metrics to senior leadership
Support the development and usage of a Supply Chain knowledge management system
Support the team in developing processes and capabilities needed to ensure standardized project management throughout the organization

Requirements:
What you must have:

Bachelor's degree from an accredited college or university in Business, Engineering, Supply Chain or related field of study
5+ years Of Supply Chain and Project Management experience preferred.

Demonstrated ability to analyze risk and interdependencies across multiple large scale, capital projects
Must be able to create high-quality professional MS PowerPoint presentations and have the ability to construct results that "tell a story" that can influence key decisions with facts
Prior experience with SAP, data visualization software (Tableau, PowerBI, etc.), project management software (Planview, Confluence, etc.) and Think-cell software is preferred
Flexible and able to push forward required decisions despite ambiguity and changing priorities
Detailed and deadline-orientated to meet regular and periodic needs of the business
High level of attention to detail and strong capability to review & sense-check results to ensure accuracy
Demonstrated strong communication skills and ability to lead a cross functional team
Ability to interact & collaborate comfortably with other teams and at all levels of the organization
Ability to follow KDP policies and procedures as well as our Values
        """,
        job_type=[JobType.FULL_TIME],
        compensation=Compensation(
            interval=CompensationInterval.YEARLY,
            min_amount=110000,  # Estimated values since not provided in job posting
            max_amount=140000,
            currency="USD"
        ),
        date_posted=datetime.now(),  # Changed from datetime.now().date() to datetime.now()
        date_scraped=datetime.now(),
        is_remote=False,
        emails=None,
        status="new"
    )
    return job

async def test_resume_generation():
    """Test the resume generation pipeline for the KDP job."""
    # Connect to MongoDB
    connected = await mongodb.connect()
    if not connected:
        logger.error("Failed to connect to MongoDB")
        return
    
    try:
        # Create test data
        profile = await create_test_profile()
        job = await create_kdp_job()
        
        # Set up resume generation components
        analyzer = JobAnalyzer()
        matcher = ProfileMatcher(analyzer)
        generator = ResumeGenerator(job_analyzer=analyzer, profile_matcher=matcher)
        
        # Step 1: Analyze job
        logger.info("Analyzing KDP job...")
        job_analysis = await analyzer.analyze_job(job)
        job.analysis = job_analysis
        
        logger.info(f"Job analysis complete. Extracted {len(job_analysis.get('skills', []))} skills.")
        logger.info("Key skills extracted:")
        for skill in job_analysis.get("skills", [])[:10]:
            logger.info(f"- {skill['name']} (Relevance: {skill['relevance']}/10)")
        
        # Step 2: Match profile to job
        logger.info("\nMatching Michael Reeves' profile to KDP job...")
        match_results = await matcher.match_profile_to_job(profile, job)
        
        logger.info(f"Match results: {match_results['overall_match']}% overall match ({match_results['fit_category']} fit)")
        logger.info(f"Skill match: {match_results['skill_match']['score']}%")
        logger.info(f"Experience match: {match_results['experience_match']['score'] * 100}%")
        logger.info(f"Education match: {match_results['education_match']['score'] * 100}%")
        
        logger.info("\nMatched skills:")
        for skill in match_results["skill_match"]["matched_skills"][:5]:
            logger.info(f"- {skill['skill_name']} (Match score: {skill['match_score']})")
        
        logger.info("\nMissing skills:")
        for skill in match_results["missing_skills"][:5]:
            logger.info(f"- {skill['name']}")
        
        # Step 3: Generate resume
        logger.info("\nGenerating tailored resume for KDP position...")
        resume_doc = await generator.generate_resume(profile, job)
        
        logger.info(f"Resume generated successfully: {resume_doc.file_path}")
        logger.info(f"Overall match score: {resume_doc.customization['match_score']}%")
        logger.info(f"Top skills highlighted: {', '.join(resume_doc.customization['highlighted_skills'])}")
        
        # Success!
        logger.info("\nResume generation pipeline test completed successfully!")
        logger.info(f"Resume saved to: {resume_doc.file_path}")
        
    except Exception as e:
        logger.error(f"Error during resume generation test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Disconnect from MongoDB
    await mongodb.disconnect()

if __name__ == "__main__":
    asyncio.run(test_resume_generation())