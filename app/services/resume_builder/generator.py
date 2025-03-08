# app/services/resume_builder/generator.py

import logging
import os
import json
import re
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

from app.core.models import JobPost, UserProfile, ResumeDocument
from app.services.resume_builder.analyzer import JobAnalyzer
from app.services.resume_builder.matcher import ProfileMatcher
from app.services.resume_builder.template import ResumeTemplate
from app.services.llm.provider import LLMProvider, LLMProviderFactory
from app.config import settings
from app.db.repositories.resumes import ResumesRepository
from app.services.resume_builder.pdf_generator import generate_resume_pdf

logger = logging.getLogger(__name__)

class ResumeGenerator:
    """Generates customized resumes based on job requirements and user profiles."""
    
    def __init__(self, 
                 llm_provider: Optional[LLMProvider] = None,
                 job_analyzer: Optional[JobAnalyzer] = None,
                 profile_matcher: Optional[ProfileMatcher] = None,
                 resumes_repository: Optional[ResumesRepository] = None):
        """Initialize resume generator.
        
        Args:
            llm_provider: LLM provider for text generation
            job_analyzer: Job analyzer for analyzing requirements
            profile_matcher: Profile matcher for matching profiles to jobs
            resumes_repository: Repository for storing generated resumes
        """
        self.llm_provider = llm_provider or LLMProviderFactory.get_provider(
            settings.LLM.PROVIDER,
            model=settings.LLM.MODEL,
            api_key=settings.LLM.API_KEY,
            api_base=settings.LLM.API_BASE
        )
        self.job_analyzer = job_analyzer or JobAnalyzer(llm_provider=self.llm_provider)
        self.profile_matcher = profile_matcher or ProfileMatcher(job_analyzer=self.job_analyzer)
        self.resumes_repository = resumes_repository or ResumesRepository()
    
    async def generate_resume(self, 
                            user_profile: UserProfile, 
                            job: JobPost, 
                            template_name: Optional[str] = None) -> ResumeDocument:
        """Generate a customized resume for a specific job.
        
        Args:
            user_profile: User profile
            job: Target job posting
            template_name: Resume template name (optional)
            
        Returns:
            Generated resume document
        """
        # Step 1: Analyze job if not already analyzed
        if not job.analysis:
            job.analysis = await self.job_analyzer.analyze_job(job)
        
        # Step 2: Match profile to job
        match_results = await self.profile_matcher.match_profile_to_job(user_profile, job)
        
        # Step 3: Load template
        template = ResumeTemplate(template_name)
        
        # Step 4: Generate resume content
        resume_content = await self._generate_resume_content(user_profile, job, match_results, template)
        
        # Step 5: Format resume as document
        resume_file_path, file_name, file_format = await self._format_resume(resume_content, template, user_profile, job)
        
        # Step 6: Create resume document
        resume_doc = ResumeDocument(
            user_id=user_profile.id,
            job_id=job.id,
            file_path=resume_file_path,
            file_name=file_name,
            file_format=file_format,
            customization={
                "template": template.template_name,
                "match_score": match_results["overall_match"],
                "fit_category": match_results["fit_category"],
                "generated_at": datetime.utcnow().isoformat(),
                "highlighted_skills": [skill["skill_name"] for skill in match_results["skill_match"]["matched_skills"][:5]]
            },
            created_at=datetime.utcnow()
        )
        
        # Step 7: Save to database
        resume_id = await self.resumes_repository.insert(resume_doc)
        resume_doc.id = resume_id
        
        return resume_doc
    
    async def _generate_resume_content(self, 
                                     user_profile: UserProfile, 
                                     job: JobPost,
                                     match_results: Dict[str, Any],
                                     template: ResumeTemplate) -> Dict[str, Any]:
        """Generate content for each section of the resume.
        
        Args:
            user_profile: User profile
            job: Target job posting
            match_results: Profile matching results
            template: Resume template
            
        Returns:
            Dictionary with content for each resume section
        """
        # Get section order from template
        sections = template.get_section_order()
        resume_content = {}
        
        # Generate header section
        resume_content["header"] = {
            "name": f"{user_profile.name.get('first', '')} {user_profile.name.get('last', '')}",
            "title": self._customize_title(user_profile.title, job.title),
            "contact": {
                "email": user_profile.contact.email,
                "phone": user_profile.contact.phone,
                "location": user_profile.contact.location.display_location() if user_profile.contact.location else "",
                "linkedin": user_profile.contact.linkedin,
                "website": user_profile.contact.website
            }
        }
        
        # Generate summary section
        resume_content["summary"] = await self._generate_summary(user_profile, job, match_results)
        
        # Generate skills section
        resume_content["skills"] = await self._generate_skills_section(user_profile, job, match_results)
        
        # Generate experience section
        resume_content["experience"] = await self._generate_experience_section(user_profile, job, match_results)
        
        # Generate education section
        resume_content["education"] = user_profile.education
        
        # Generate certifications section
        resume_content["certifications"] = user_profile.certifications
        
        return resume_content
    
    def _customize_title(self, user_title: str, job_title: str) -> str:
        """Customize professional title to align with job title.
        
        Args:
            user_title: User's professional title
            job_title: Target job title
            
        Returns:
            Customized professional title
        """
        # If titles are already similar, keep user's title
        user_title_lower = user_title.lower()
        job_title_lower = job_title.lower()
        
        if user_title_lower == job_title_lower:
            return user_title
        
        # Extract core job title without level/seniority
        job_core = re.sub(r'^(senior|lead|principal|staff|junior|associate)\s+', '', job_title_lower)
        job_core = re.sub(r'\s+(i|ii|iii|iv|v)$', '', job_core)
        
        user_core = re.sub(r'^(senior|lead|principal|staff|junior|associate)\s+', '', user_title_lower)
        user_core = re.sub(r'\s+(i|ii|iii|iv|v)$', '', user_core)
        
        # If core titles match, adapt user title to job seniority
        if job_core == user_core:
            job_level_match = re.search(r'^(senior|lead|principal|staff|junior|associate)', job_title_lower)
            if job_level_match:
                job_level = job_level_match.group(1).title()
                return f"{job_level} {user_core.title()}"
        
        # If significant overlap, use job title
        job_words = set(job_title_lower.split())
        user_words = set(user_title_lower.split())
        
        if len(job_words.intersection(user_words)) >= 2:
            return job_title
        
        # For dissimilar titles, keep user's title to avoid misrepresentation
        return user_title
    
    async def _generate_summary(self, 
                              user_profile: UserProfile, 
                              job: JobPost,
                              match_results: Dict[str, Any]) -> str:
        """Generate customized professional summary.
        
        Args:
            user_profile: User profile
            job: Target job posting
            match_results: Profile matching results
            
        Returns:
            Tailored professional summary
        """
        existing_summary = user_profile.summary or ""
        
        # Get key job requirements
        job_skills = ", ".join([skill["name"] for skill in job.analysis.get("skills", [])[:5]])
        job_level = job.analysis.get("job_level", "mid")
        job_title = job.title
        company_name = job.company_name
        
        # Get best matching experiences
        relevant_experiences = match_results.get("relevant_experiences", [])
        experience_highlights = ""
        if relevant_experiences:
            top_experiences = relevant_experiences[:2]
            experience_highlights = ", ".join([f"{exp['title']} at {exp['company']}" for exp in top_experiences])
        
        # Craft prompt for LLM
        prompt = f"""
        Write a professional summary for a resume tailored to this job:
        
        Job Title: {job_title}
        Company: {company_name}
        Key Skills Needed: {job_skills}
        Job Level: {job_level}
        
        The person has experience as: {experience_highlights}
        
        Their current summary is:
        {existing_summary}
        
        Write a concise, powerful 3-4 sentence professional summary that:
        1. Highlights their relevant experience and skills for this specific position
        2. Uses strong action verbs and industry-specific terminology
        3. Quantifies achievements where possible
        4. Positions them as an ideal candidate for this specific role
        
        The summary should be written in first person and should not exceed 100 words.
        """
        
        try:
            summary = await self.llm_provider.generate(
                prompt=prompt,
                system_message="You are an expert resume writer who creates tailored, professional summaries that highlight a candidate's most relevant qualifications for specific jobs."
            )
            
            return summary.strip()
        except Exception as e:
            logger.error(f"Error generating summary with LLM: {str(e)}")
            # Return original summary as fallback
            return existing_summary
    
    async def _generate_skills_section(self, 
                                    user_profile: UserProfile, 
                                    job: JobPost,
                                    match_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate customized skills section.
        
        Args:
            user_profile: User profile
            job: Target job posting
            match_results: Profile matching results
            
        Returns:
            Structured skills section
        """
        # Get matched skills
        matched_skills = match_results["skill_match"]["matched_skills"]
        
        # Sort skills by relevance and categorize
        technical_skills = []
        soft_skills = []
        domain_skills = []
        
        for skill_match in matched_skills:
            skill_name = skill_match["skill_name"]
            category = skill_match.get("category", "technical")
            
            if category == "technical":
                technical_skills.append(skill_name)
            elif category == "soft":
                soft_skills.append(skill_name)
            else:
                domain_skills.append(skill_name)
        
        # Add other skills from profile that might be relevant
        for profile_skill in user_profile.skills:
            skill_name = profile_skill.name
            
            # Skip already included skills
            if skill_name in technical_skills or skill_name in soft_skills or skill_name in domain_skills:
                continue
            
            # Determine category based on common patterns
            if any(tech_term in skill_name.lower() for tech_term in [
                'programming', 'software', 'database', 'framework', 'language', 
                'platform', 'tool', 'system', 'development', 'engineering'
            ]):
                technical_skills.append(skill_name)
            elif any(soft_term in skill_name.lower() for soft_term in [
                'communication', 'leadership', 'teamwork', 'problem solving',
                'management', 'collaboration', 'organization', 'creative'
            ]):
                soft_skills.append(skill_name)
            else:
                domain_skills.append(skill_name)
        
        return {
            "technical": technical_skills[:10],  # Limit to top 10
            "soft": soft_skills[:5],            # Limit to top 5
            "domain": domain_skills[:5]         # Limit to top 5
        }
    
    async def _generate_experience_section(self, 
                                        user_profile: UserProfile, 
                                        job: JobPost,
                                        match_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate customized experience section.
        
        Args:
            user_profile: User profile
            job: Target job posting
            match_results: Profile matching results
            
        Returns:
            List of tailored experience entries
        """
        # Get relevant experiences in order of relevance
        relevant_exp_ids = [exp["company"] + exp["title"] for exp in match_results.get("relevant_experiences", [])]
        
        # Prepare tailored experiences
        tailored_experiences = []
        
        for exp in user_profile.experiences:
            exp_id = exp.company + exp.title
            
            # Determine relevance order (for sorting)
            relevance_order = relevant_exp_ids.index(exp_id) if exp_id in relevant_exp_ids else 999
            
            # Get custom achievements for highly relevant experiences
            achievements = exp.achievements
            if relevance_order < 3:  # Top 3 most relevant experiences
                achievements = await self._tailor_achievements(exp, job, match_results)
            
            tailored_experiences.append({
                "company": exp.company,
                "title": exp.title,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "description": exp.description,
                "achievements": achievements,
                "skills_used": exp.skills_used,
                "location": exp.location,
                "relevance_order": relevance_order
            })
        
        # Sort by relevance, then by date (most recent first)
        return sorted(tailored_experiences, key=lambda x: (x["relevance_order"], x.get("end_date", "9999-99") + x["start_date"]), reverse=True)
    
    async def _tailor_achievements(self, 
                                experience: Dict[str, Any], 
                                job: JobPost,
                                match_results: Dict[str, Any]) -> List[str]:
        """Tailor achievement bullets for a specific job.
        
        Args:
            experience: Experience entry
            job: Target job posting
            match_results: Profile matching results
            
        Returns:
            List of tailored achievement bullets
        """
        original_achievements = experience.get("achievements", [])
        
        # If no original achievements, return empty list
        if not original_achievements:
            return []
        
        # Get job requirements and matched skills
        job_skills = [skill["name"] for skill in job.analysis.get("skills", [])]
        matched_skills = [match["job_skill"] for match in match_results["skill_match"]["matched_skills"]]
        
        # Craft prompt for LLM
        achievement_text = "\n".join([f"- {achievement}" for achievement in original_achievements])
        
        prompt = f"""
        Rewrite these professional achievements to highlight relevance for this specific job:
        
        Job Title: {job.title}
        Key Skills Required: {', '.join(job_skills[:5])}
        
        Original Achievements:
        {achievement_text}
        
        Rewrite each achievement to:
        1. Emphasize skills and experiences most relevant to the target job
        2. Use similar terminology to the job description
        3. Quantify results where possible (maintain any existing metrics)
        4. Start with strong action verbs
        5. Be concise and impactful
        
        Keep approximately the same number of achievements. Each bullet should be one sentence and no more than 20 words.
        """
        
        try:
            result = await self.llm_provider.generate(
                prompt=prompt,
                system_message="You are an expert resume writer who tailors achievement bullets to highlight relevance for specific jobs."
            )
            
            # Extract bullet points
            tailored_achievements = []
            for line in result.strip().split("\n"):
                if line.strip().startswith("-"):
                    tailored_achievements.append(line.strip()[2:].strip())
                elif line.strip() and not line.strip().startswith("#"):
                    tailored_achievements.append(line.strip())
            
            # Ensure we have at least some achievements
            if not tailored_achievements and original_achievements:
                return original_achievements
            
            return tailored_achievements
        except Exception as e:
            logger.error(f"Error tailoring achievements with LLM: {str(e)}")
            # Return original achievements as fallback
            return original_achievements
    
    async def _format_resume(self, 
                        resume_content: Dict[str, Any],
                        template: ResumeTemplate,
                        user_profile: UserProfile,
                        job: JobPost) -> Tuple[str, str, str]:
        """Format resume content into a document file.
        
        Args:
            resume_content: Generated resume content
            template: Resume template
            user_profile: User profile
            job: Target job posting
            
        Returns:
            Tuple of (file_path, file_name, file_format)
        """
        # Create unique filename
        user_name = f"{user_profile.name.get('first', 'user')}_{user_profile.name.get('last', 'profile')}".lower()
        company_name = job.company_name.lower().replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        file_name = f"{user_name}_{company_name}_{timestamp}_{unique_id}"
        
        # Create resume directory if it doesn't exist
        resume_dir = Path(settings.STORAGE.RESUME_DIR)
        resume_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate both JSON and PDF formats
        json_path = str(resume_dir / f"{file_name}.json")
        pdf_path = str(resume_dir / f"{file_name}.pdf")
        
        # Save content as JSON
        with open(json_path, 'w') as f:
            json.dump(resume_content, f, indent=2)
        
        # Generate PDF
        try:
            pdf_path = generate_resume_pdf(resume_content, pdf_path)
            file_format = "pdf"  # Prefer PDF if generation was successful
        except Exception as e:
            logger.error(f"Error generating PDF resume: {str(e)}. Using JSON format instead.")
            file_format = "json"
            pdf_path = json_path
        
        return pdf_path, file_name, file_format