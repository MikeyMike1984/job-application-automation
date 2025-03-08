# app/services/resume_builder/analyzer.py

import logging
import re
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from app.core.models import JobPost, UserProfile
from app.services.llm.provider import LLMProvider, LLMProviderFactory
from app.config import settings

logger = logging.getLogger(__name__)

class JobAnalyzer:
    """Analyzes job descriptions to extract key requirements and information."""
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """Initialize job analyzer.
        
        Args:
            llm_provider: LLM provider for text analysis. If None, creates default provider.
        """
        self.llm_provider = llm_provider or LLMProviderFactory.get_provider(
            settings.LLM.PROVIDER,
            model=settings.LLM.MODEL,
            api_key=settings.LLM.API_KEY,
            api_base=settings.LLM.API_BASE
        )
        
    async def analyze_job(self, job: JobPost) -> Dict[str, Any]:
        """Analyze job posting to extract key information.
        
        Args:
            job: Job posting to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        if not job.description:
            logger.warning(f"Job {job.id} has no description to analyze")
            return {
                "skills": [],
                "experience_years": None,
                "education": [],
                "job_level": None,
                "keywords": [],
                "analysis_summary": "No description available for analysis"
            }
            
        # Extract information using both rule-based and LLM approaches
        skills = await self._extract_skills(job.description, job.title)
        experience = await self._extract_experience(job.description)
        education = await self._extract_education(job.description)
        job_level = await self._extract_job_level(job.title, job.description)
        keywords = await self._extract_keywords(job.description)
        
        # Get comprehensive analysis using LLM
        analysis_summary = await self._get_analysis_summary(job)
        
        return {
            "skills": skills,
            "experience_years": experience,
            "education": education,
            "job_level": job_level,
            "keywords": keywords,
            "analysis_summary": analysis_summary,
            "analyzed_at": datetime.utcnow()
        }
    
    async def _extract_skills(self, description: str, title: str) -> List[Dict[str, Any]]:
        """Extract technical and soft skills from job description.
        
        Args:
            description: Job description text
            title: Job title
            
        Returns:
            List of extracted skills with relevance scores
        """
        # Define the schema for the LLM response
        schema = {
            "type": "object",
            "required": ["skills"],
            "properties": {
                "skills": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "category", "relevance"],
                        "properties": {
                            "name": {"type": "string"},
                            "category": {"type": "string", "enum": ["technical", "soft", "domain"]},
                            "relevance": {"type": "integer", "minimum": 1, "maximum": 10},
                            "years_required": {"type": ["integer", "null"]}
                        }
                    }
                }
            }
        }
        
        # Create a prompt for the LLM
        prompt = f"""
        Extract all skills mentioned in the following job description:
        
        Job Title: {title}
        
        Job Description:
        {description}
        
        For each skill:
        1. Identify if it's a technical skill (programming languages, tools, platforms), soft skill (communication, leadership), or domain knowledge (industry-specific).
        2. Assign a relevance score (1-10) based on how important it appears to be for the role.
        3. If years of experience with the skill are mentioned, note that as well.
        
        Focus on extracting actual skills rather than general job requirements.
        """
        
        try:
            result = await self.llm_provider.generate_structured(
                prompt=prompt,
                output_schema=schema,
                system_message="You are an expert job analyst who extracts key information from job descriptions accurately."
            )
            
            return result.get("skills", [])
        except Exception as e:
            logger.error(f"Error extracting skills with LLM: {str(e)}")
            # Fallback to rule-based extraction
            return self._rule_based_skill_extraction(description)
    
    def _rule_based_skill_extraction(self, description: str) -> List[Dict[str, Any]]:
        """Extract skills using rule-based approach as fallback.
        
        Args:
            description: Job description text
            
        Returns:
            List of extracted skills
        """
        # Common technical skills regex patterns
        tech_skills_patterns = [
            r'Python', r'Java', r'JavaScript', r'React', r'Node\.js', r'SQL', r'AWS',
            r'Docker', r'Kubernetes', r'Git', r'C\+\+', r'C#', r'Azure', r'GCP',
            r'HTML', r'CSS', r'TypeScript', r'MongoDB', r'PostgreSQL', r'Jenkins',
            r'CI/CD', r'REST API', r'GraphQL', r'Machine Learning', r'TensorFlow',
            r'PyTorch', r'Data Science', r'Agile', r'Scrum', r'DevOps'
        ]
        
        # Common soft skills regex patterns
        soft_skills_patterns = [
            r'teamwork', r'communication', r'leadership', r'problem.solving',
            r'critical.thinking', r'collaboration', r'adaptability', r'time.management',
            r'creativity', r'attention.to.detail', r'project.management'
        ]
        
        results = []
        
        # Extract technical skills
        for skill in tech_skills_patterns:
            if re.search(r'\b' + skill + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill,
                    "category": "technical",
                    "relevance": 7,  # Default medium-high relevance
                    "years_required": None
                })
        
        # Extract soft skills
        for skill in soft_skills_patterns:
            if re.search(r'\b' + skill + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill.replace('.', ' '),
                    "category": "soft",
                    "relevance": 5,  # Default medium relevance
                    "years_required": None
                })
        
        return results
    
    async def _extract_experience(self, description: str) -> Optional[int]:
        """Extract years of experience required from job description.
        
        Args:
            description: Job description text
            
        Returns:
            Years of experience required, or None if not specified
        """
        # First try rule-based extraction
        experience_patterns = [
            r'(\d+)\+?\s*(?:years|yrs)(?:\s*of\s*|\s+)(?:experience|exp)',
            r'(?:experience|exp)(?:\s*of\s*|\s+)(\d+)\+?\s*(?:years|yrs)',
            r'(\d+)\+?\s*(?:years|yrs)(?:\s*|\s+)(?:experience|exp)',
            r'(?:minimum|min)(?:\s+)(?:of\s+)?(\d+)(?:\+)?\s*(?:years|yrs)'
        ]
        
        for pattern in experience_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        
        # If rule-based extraction fails, use LLM
        prompt = f"""
        Extract the minimum years of experience required from this job description:
        
        {description}
        
        Return ONLY a number representing years of experience (e.g., 5). If no specific years of experience are mentioned, return null.
        """
        
        try:
            schema = {
                "type": "object",
                "properties": {
                    "years": {"type": ["integer", "null"]}
                }
            }
            
            result = await self.llm_provider.generate_structured(
                prompt=prompt,
                output_schema=schema,
                system_message="You are an expert job analyst who extracts key information from job descriptions accurately."
            )
            
            return result.get("years")
        except Exception as e:
            logger.error(f"Error extracting experience with LLM: {str(e)}")
            return None
    
    async def _extract_education(self, description: str) -> List[Dict[str, str]]:
        """Extract education requirements from job description.
        
        Args:
            description: Job description text
            
        Returns:
            List of education requirements
        """
        schema = {
            "type": "object",
            "required": ["education"],
            "properties": {
                "education": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["level", "field", "required"],
                        "properties": {
                            "level": {"type": "string"},
                            "field": {"type": "string"},
                            "required": {"type": "boolean"}
                        }
                    }
                }
            }
        }
        
        prompt = f"""
        Extract education requirements from this job description:
        
        {description}
        
        For each education requirement, identify:
        1. The degree level (e.g., Bachelor's, Master's, Ph.D., High School)
        2. The field of study (e.g., Computer Science, Engineering, Business)
        3. Whether it's required or preferred
        
        If no education requirements are specified, return an empty array.
        """
        
        try:
            result = await self.llm_provider.generate_structured(
                prompt=prompt,
                output_schema=schema,
                system_message="You are an expert job analyst who extracts key information from job descriptions accurately."
            )
            
            return result.get("education", [])
        except Exception as e:
            logger.error(f"Error extracting education with LLM: {str(e)}")
            return []
    
    async def _extract_job_level(self, title: str, description: str) -> str:
        """Extract job level/seniority from job description.
        
        Args:
            title: Job title
            description: Job description text
            
        Returns:
            Job level (entry, mid, senior, principal, executive)
        """
        # First check the title for common level indicators
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['senior', 'sr.', 'sr ', 'lead']):
            return "senior"
        elif any(word in title_lower for word in ['principal', 'staff', 'architect']):
            return "principal"
        elif any(word in title_lower for word in ['director', 'head', 'vp', 'chief']):
            return "executive"
        elif any(word in title_lower for word in ['junior', 'jr.', 'jr ', 'associate', 'entry']):
            return "entry"
        
        # If title doesn't have clear indicators, use LLM
        schema = {
            "type": "object",
            "required": ["level"],
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["entry", "mid", "senior", "principal", "executive"]
                }
            }
        }
        
        prompt = f"""
        Determine the job level/seniority based on this job title and description:
        
        Title: {title}
        
        Description:
        {description}
        
        Select the most appropriate level from:
        - entry (0-2 years experience, junior roles)
        - mid (3-5 years experience, regular individual contributor)
        - senior (5-8 years experience, senior individual contributor)
        - principal (8+ years experience, staff/principal/architect roles)
        - executive (management, director, VP level)
        """
        
        try:
            result = await self.llm_provider.generate_structured(
                prompt=prompt,
                output_schema=schema,
                system_message="You are an expert job analyst who extracts key information from job descriptions accurately."
            )
            
            return result.get("level", "mid")
        except Exception as e:
            logger.error(f"Error extracting job level with LLM: {str(e)}")
            # Default to mid-level if extraction fails
            return "mid"
    
    async def _extract_keywords(self, description: str) -> List[str]:
        """Extract important keywords from job description.
        
        Args:
            description: Job description text
            
        Returns:
            List of keywords
        """
        schema = {
            "type": "object",
            "required": ["keywords"],
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
        
        prompt = f"""
        Extract 10-15 important keywords from this job description that would be valuable to include in a resume. Focus on industry terms, technologies, methodologies, and specific skills mentioned.
        
        Job Description:
        {description}
        """
        
        try:
            result = await self.llm_provider.generate_structured(
                prompt=prompt,
                output_schema=schema,
                system_message="You are an expert job analyst who extracts key information from job descriptions accurately."
            )
            
            return result.get("keywords", [])
        except Exception as e:
            logger.error(f"Error extracting keywords with LLM: {str(e)}")
            return []
    
    async def _get_analysis_summary(self, job: JobPost) -> str:
        """Generate a comprehensive analysis summary of the job.
        
        Args:
            job: Job posting
            
        Returns:
            Analysis summary text
        """
        prompt = f"""
        Provide a comprehensive analysis of this job posting:
        
        Job Title: {job.title}
        Company: {job.company_name}
        Location: {job.location.display_location() if job.location else 'Not specified'}
        
        Description:
        {job.description}
        
        Your analysis should include:
        1. The main responsibilities of the role
        2. Key technical skills required
        3. Experience level expected
        4. Company culture indicators
        5. Job benefits and perks (if mentioned)
        6. Any red flags or concerns
        
        Keep your analysis concise but insightful.
        """
        
        try:
            summary = await self.llm_provider.generate(
                prompt=prompt,
                system_message="You are an expert job market analyst and career coach. Provide insightful, accurate, and concise analysis of job postings."
            )
            
            return summary
        except Exception as e:
            logger.error(f"Error generating analysis summary with LLM: {str(e)}")
            return "Analysis unavailable due to error in processing."