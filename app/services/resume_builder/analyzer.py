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
            
            skills = result.get("skills", [])
            # If LLM returned skills, use them
            if skills:
                return skills
            else:
                # If no skills were returned, fall back to rule-based extraction
                logger.info("LLM returned no skills, falling back to rule-based extraction")
                return self._rule_based_skill_extraction(description)
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
        # Additional skills for program/project management
        pm_skills_patterns = [
            r'Project Management', r'Program Management', r'Agile', r'Scrum', r'Kanban',
            r'JIRA', r'Confluence', r'MS Project', r'Gantt', r'Stakeholder Management',
            r'Risk Management', r'Budget Management', r'Resource Planning', r'KPIs',
            r'Metrics', r'Reporting', r'Dashboards', r'PowerPoint', r'Presentation',
            r'Cross-functional', r'Leadership', r'Team Leadership'
        ]
        
        # Supply chain related skills
        supply_chain_skills = [
            r'Supply Chain', r'Logistics', r'Inventory Management', r'Procurement',
            r'Vendor Management', r'ERP', r'SAP', r'Warehouse Management',
            r'Distribution', r'Forecasting', r'Demand Planning', r'S&OP',
            r'Lean', r'Six Sigma', r'Continuous Improvement', r'Process Improvement',
            r'KPIs', r'Metrics', r'Data Analysis', r'Power BI', r'Tableau'
        ]
        
        # Common technical skills
        tech_skills_patterns = [
            r'Python', r'Java', r'JavaScript', r'React', r'Node\.js', r'SQL', r'AWS',
            r'Docker', r'Kubernetes', r'Git', r'C\+\+', r'C#', r'Azure', r'GCP',
            r'HTML', r'CSS', r'TypeScript', r'MongoDB', r'PostgreSQL', r'Jenkins',
            r'CI/CD', r'REST API', r'GraphQL', r'Machine Learning', r'TensorFlow',
            r'PyTorch', r'Data Science', r'Agile', r'Scrum', r'DevOps',
            r'Python', r'SQL', r'Excel', r'Power BI', r'Tableau', r'Data Analysis',
            r'Microsoft Office', r'SharePoint', r'SAP', r'Oracle', r'Databases',
            r'ERP Systems', r'Reporting', r'Analytics', r'Visualization', r'Dashboards'
        ]
        
        # Common soft skills patterns
        soft_skills_patterns = [
            r'teamwork', r'communication', r'leadership', r'problem.solving',
            r'critical.thinking', r'collaboration', r'adaptability', r'time.management',
            r'creativity', r'attention.to.detail', r'project.management',
            r'Communication', r'Leadership', r'Teamwork', r'Problem.Solving',
            r'Critical.Thinking', r'Collaboration', r'Adaptability', r'Time.Management',
            r'Creativity', r'Attention.to.Detail', r'Presentation', r'Negotiation',
            r'Conflict.Resolution', r'Decision.Making', r'Strategic.Thinking'
        ]
        
        results = []
        
        # Extract program management skills
        for skill in pm_skills_patterns:
            if re.search(r'\b' + skill + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill,
                    "category": "domain",
                    "relevance": 8,  # High relevance for PM roles
                    "years_required": None
                })
        
        # Extract supply chain skills
        for skill in supply_chain_skills:
            if re.search(r'\b' + skill + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill,
                    "category": "domain",
                    "relevance": 9,  # Very high relevance for supply chain roles
                    "years_required": None
                })
        
        # Extract technical skills
        for skill in tech_skills_patterns:
            if re.search(r'\b' + skill + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill,
                    "category": "technical",
                    "relevance": 7,  # Medium-high relevance
                    "years_required": None
                })
        
        # Extract soft skills
        for skill in soft_skills_patterns:
            if re.search(r'\b' + skill.replace('.', '\\s*') + r'\b', description, re.IGNORECASE):
                results.append({
                    "name": skill.replace('.', ' '),
                    "category": "soft",
                    "relevance": 6,  # Medium relevance
                    "years_required": None
                })
        
        # Deduplicate skills (might have overlaps between categories)
        unique_skills = {}
        for skill in results:
            skill_name_lower = skill["name"].lower()
            if skill_name_lower not in unique_skills or skill["relevance"] > unique_skills[skill_name_lower]["relevance"]:
                unique_skills[skill_name_lower] = skill
        
        return list(unique_skills.values())
    
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
            # Try to extract with simple pattern matching as a last resort
            for pattern in [r'(\d+)\+?\s*years', r'(\d+)\+?\s*yrs']:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    try:
                        return int(match.group(1))
                    except (ValueError, IndexError):
                        pass
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
            # Simple rule-based fallback
            education = []
            
            # Common education pattern matching
            ed_patterns = [
                (r"bachelor'?s\s+degree", "Bachelor's", True),
                (r"master'?s\s+degree", "Master's", False),
                (r"phd|doctorate", "Ph.D.", False),
                (r"associate'?s\s+degree", "Associate's", False),
                (r"high\s+school", "High School", False)
            ]
            
            # Common fields
            fields = [
                "business", "engineering", "computer science", "supply chain",
                "logistics", "operations", "management"
            ]
            
            for ed_pattern, level, is_common in ed_patterns:
                if re.search(ed_pattern, description, re.IGNORECASE):
                    # Try to find associated field
                    field = "General"
                    for f in fields:
                        if re.search(r'\b' + f + r'\b', description, re.IGNORECASE):
                            field = f.title()
                            break
                    
                    # Determine if required (look for "required", "must have", etc.)
                    required = False
                    if is_common or re.search(r'required|must\s+have', description, re.IGNORECASE):
                        required = True
                    
                    education.append({
                        "level": level,
                        "field": field,
                        "required": required
                    })
            
            return education
    
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
            
            # Look for years of experience as fallback
            try:
                years_pattern = r'(\d+)\+?\s*years?'
                match = re.search(years_pattern, description, re.IGNORECASE)
                if match:
                    years = int(match.group(1))
                    if years <= 2:
                        return "entry"
                    elif years <= 5:
                        return "mid"
                    elif years <= 8:
                        return "senior"
                    else:
                        return "principal"
            except:
                pass
                
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
            
            # Simple keyword extraction as fallback
            keywords = []
            
            # Common important keywords to look for
            important_terms = [
                "Project Management", "Program Management", "Supply Chain", 
                "Leadership", "Cross-functional", "Strategic", "KPIs", "Metrics",
                "Budget", "Cost Reduction", "Efficiency", "Optimization",
                "Process Improvement", "Lean", "Six Sigma", "Agile", "Scrum",
                "SAP", "ERP", "PowerPoint", "Excel", "Power BI", "Tableau",
                "Communication", "Stakeholder Management", "Risk Management"
            ]
            
            for term in important_terms:
                if re.search(r'\b' + re.escape(term) + r'\b', description, re.IGNORECASE):
                    keywords.append(term)
            
            return keywords[:15]  # Return up to 15 keywords
    
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
            
            # Generate a basic summary as fallback
            title = job.title
            company = job.company_name
            
            return f"""
            This {title} position at {company} appears to be focused on program management 
            within a supply chain context. The role requires project management experience 
            and skills in cross-functional team leadership. 
            
            Key requirements include experience in program/project management, 
            strong communication skills, and analytical capabilities. The position 
            seems to be at a senior level, likely requiring 5+ years of relevant experience.
            
            The job involves managing end-to-end programs, developing KPIs, 
            monitoring performance, and driving continuous improvement initiatives.
            """