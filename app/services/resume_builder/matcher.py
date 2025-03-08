# app/services/resume_builder/matcher.py

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from app.core.models import JobPost, UserProfile, ProfileSkill, ProfileExperience
from app.services.resume_builder.analyzer import JobAnalyzer

logger = logging.getLogger(__name__)

class ProfileMatcher:
    """Matches user profiles against job requirements."""
    
    def __init__(self, job_analyzer: Optional[JobAnalyzer] = None):
        """Initialize profile matcher.
        
        Args:
            job_analyzer: Job analyzer for analyzing job requirements
        """
        self.job_analyzer = job_analyzer or JobAnalyzer()
    
    async def match_profile_to_job(self, profile: UserProfile, job: JobPost) -> Dict[str, Any]:
        """Match a user profile against a job and calculate relevance scores.
        
        Args:
            profile: User profile
            job: Job posting
            
        Returns:
            Dictionary with matching results and scores
        """
        # First, analyze the job if it doesn't have analysis data
        if not job.analysis:
            job.analysis = await self.job_analyzer.analyze_job(job)
        
        # Get job requirements
        job_skills = job.analysis.get("skills", [])
        job_experience = job.analysis.get("experience_years")
        job_education = job.analysis.get("education", [])
        job_level = job.analysis.get("job_level", "mid")
        
        # Match skills
        skill_matches = await self._match_skills(profile.skills, job_skills)
        
        # Match experience
        experience_match = await self._match_experience(profile.experiences, job_experience, job_skills)
        
        # Match education
        education_match = await self._match_education(profile.education, job_education)
        
        # Calculate overall match score (0-100)
        skill_score = sum(match["relevance_score"] for match in skill_matches) / max(len(job_skills), 1) * 100
        experience_score = experience_match.get("score", 0) * 100
        education_score = education_match.get("score", 0) * 100
        
        # Calculate weighted scores (skills 50%, experience 30%, education 20%)
        overall_score = (skill_score * 0.5) + (experience_score * 0.3) + (education_score * 0.2)
        
        # Get the best matching experiences for this job
        relevant_experiences = await self._rank_experiences(profile.experiences, job_skills, job_level)
        
        # Determine fit categorization
        fit_category = self._determine_fit_category(overall_score)
        
        return {
            "overall_match": round(overall_score, 2),
            "fit_category": fit_category,
            "skill_match": {
                "score": round(skill_score, 2),
                "matched_skills": skill_matches
            },
            "experience_match": experience_match,
            "education_match": education_match,
            "relevant_experiences": relevant_experiences,
            "missing_skills": [skill for skill in job_skills if not any(
                match["skill_name"].lower() == skill["name"].lower() for match in skill_matches
            )],
            "matched_at": datetime.utcnow()
        }
    
    async def _match_skills(self, profile_skills: List[ProfileSkill], 
                          job_skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match user skills against job required skills.
        
        Args:
            profile_skills: List of user's skills
            job_skills: List of job required skills
            
        Returns:
            List of matched skills with scores
        """
        matched_skills = []
        
        for job_skill in job_skills:
            job_skill_name = job_skill["name"].lower()
            relevance = job_skill.get("relevance", 5)
            years_required = job_skill.get("years_required")
            
            # Find the matching user skill
            best_match = None
            best_match_score = 0
            
            for profile_skill in profile_skills:
                profile_skill_name = profile_skill.name.lower()
                
                # Check for exact match or partial match
                if job_skill_name == profile_skill_name:
                    match_score = 1.0
                elif job_skill_name in profile_skill_name or profile_skill_name in job_skill_name:
                    # Partial match based on string length ratio
                    match_score = min(len(job_skill_name), len(profile_skill_name)) / max(len(job_skill_name), len(profile_skill_name))
                else:
                    # Check for word-level matches
                    job_skill_words = set(job_skill_name.split())
                    profile_skill_words = set(profile_skill_name.split())
                    common_words = job_skill_words.intersection(profile_skill_words)
                    
                    if common_words:
                        match_score = len(common_words) / len(job_skill_words)
                    else:
                        continue  # No match
                
                # Check years of experience if required
                if years_required and profile_skill.years:
                    if profile_skill.years >= years_required:
                        experience_factor = 1.0
                    else:
                        experience_factor = profile_skill.years / years_required
                    
                    # Adjust match score based on experience
                    match_score = match_score * 0.7 + experience_factor * 0.3
                
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match = profile_skill
            
            if best_match and best_match_score >= 0.6:  # Threshold for considering a match
                matched_skills.append({
                    "job_skill": job_skill["name"],
                    "skill_name": best_match.name,
                    "category": job_skill.get("category", "technical"),
                    "match_score": round(best_match_score, 2),
                    "years_experience": best_match.years,
                    "years_required": years_required,
                    "relevance_score": round(best_match_score * (relevance / 10), 2)  # Scale by job skill relevance
                })
        
        # Sort by relevance score descending
        return sorted(matched_skills, key=lambda x: x["relevance_score"], reverse=True)
    
    async def _match_experience(self, profile_experiences: List[ProfileExperience], 
                              job_experience: Optional[int],
                              job_skills: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Match user experience against job required experience.
        
        Args:
            profile_experiences: List of user's experiences
            job_experience: Years of experience required for the job
            job_skills: List of job required skills
            
        Returns:
            Dictionary with experience matching results
        """
        if not profile_experiences:
            return {
                "score": 0,
                "total_years": 0,
                "required_years": job_experience,
                "has_sufficient_experience": False
            }
        
        # Calculate total years of experience
        total_years = 0
        relevant_years = 0
        
        for exp in profile_experiences:
            # Calculate duration for this experience
            start_date = datetime.strptime(exp.start_date, "%Y-%m")
            
            if exp.end_date:
                end_date = datetime.strptime(exp.end_date, "%Y-%m")
            else:
                end_date = datetime.now()
            
            duration_years = (end_date.year - start_date.year) + (end_date.month - start_date.month) / 12
            total_years += duration_years
            
            # Check if experience is relevant to job skills
            relevance_score = 0
            for job_skill in job_skills:
                skill_name = job_skill["name"].lower()
                
                # Check title, description and skills used
                if (skill_name in exp.title.lower() or
                    (exp.description and skill_name in exp.description.lower()) or
                    any(skill_name in skill.lower() for skill in exp.skills_used)):
                    relevance_score += job_skill.get("relevance", 5) / 10
            
            # Normalize relevance score to 0-1 range
            if job_skills:
                relevance_score = min(relevance_score / len(job_skills), 1.0)
            else:
                relevance_score = 0.5  # Default if no job skills specified
            
            # Add weighted years to relevant experience
            relevant_years += duration_years * relevance_score
        
        # Calculate experience match score
        if job_experience:
            if relevant_years >= job_experience:
                experience_score = 1.0
            else:
                experience_score = relevant_years / job_experience
        else:
            # If no specific experience requirement, use a standard scale
            if relevant_years >= 7:
                experience_score = 1.0
            elif relevant_years >= 5:
                experience_score = 0.9
            elif relevant_years >= 3:
                experience_score = 0.8
            elif relevant_years >= 1:
                experience_score = 0.6
            else:
                experience_score = 0.3
        
        return {
            "score": round(experience_score, 2),
            "total_years": round(total_years, 1),
            "relevant_years": round(relevant_years, 1),
            "required_years": job_experience,
            "has_sufficient_experience": relevant_years >= (job_experience if job_experience else 3)
        }
    
    async def _match_education(self, profile_education: List[Dict[str, Any]], 
                             job_education: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Match user education against job required education.
        
        Args:
            profile_education: List of user's education
            job_education: List of job required education
            
        Returns:
            Dictionary with education matching results
        """
        if not job_education:
            # If no specific education requirements, assume a basic match
            return {
                "score": 0.8,
                "has_required_education": True,
                "matches": []
            }
        
        if not profile_education:
            return {
                "score": 0,
                "has_required_education": False,
                "matches": []
            }
        
        # Define degree levels for comparison
        degree_levels = {
            "high school": 1,
            "associate": 2,
            "bachelor": 3,
            "master": 4,
            "mba": 4,
            "phd": 5,
            "doctorate": 5
        }
        
        matches = []
        best_match_score = 0
        has_required = False
        
        for job_edu in job_education:
            job_level = job_edu["level"].lower()
            job_field = job_edu["field"].lower()
            is_required = job_edu["required"]
            
            job_level_score = 0
            for level_name, level_score in degree_levels.items():
                if level_name in job_level:
                    job_level_score = level_score
                    break
            
            # Find best matching education from profile
            for profile_edu in profile_education:
                profile_level = profile_edu.get("degree", "").lower()
                profile_field = profile_edu.get("field", "").lower()
                
                # Determine profile level score
                profile_level_score = 0
                for level_name, level_score in degree_levels.items():
                    if level_name in profile_level:
                        profile_level_score = level_score
                        break
                
                # Level match score
                if profile_level_score >= job_level_score:
                    level_match = 1.0
                else:
                    level_match = profile_level_score / max(job_level_score, 1)
                
                # Field match score
                if job_field in profile_field or profile_field in job_field:
                    field_match = 1.0
                else:
                    # Check for word-level matches
                    job_field_words = set(job_field.split())
                    profile_field_words = set(profile_field.split())
                    common_words = job_field_words.intersection(profile_field_words)
                    
                    if common_words:
                        field_match = len(common_words) / len(job_field_words)
                    else:
                        field_match = 0.0
                
                # Combined match score (70% level, 30% field)
                match_score = level_match * 0.7 + field_match * 0.3
                
                if match_score > 0.6:  # Threshold for considering a match
                    matches.append({
                        "job_requirement": f"{job_level} in {job_field}",
                        "user_education": f"{profile_level} in {profile_field}",
                        "match_score": round(match_score, 2),
                        "required": is_required
                    })
                    
                    if match_score > best_match_score:
                        best_match_score = match_score
                    
                    if is_required and match_score > 0.8:
                        has_required = True
        
        # If no required education or all required education is matched
        if not any(edu["required"] for edu in job_education) or has_required:
            education_score = best_match_score
        else:
            education_score = best_match_score * 0.5  # Penalize for missing required education
        
        return {
            "score": round(education_score, 2),
            "has_required_education": has_required or not any(edu["required"] for edu in job_education),
            "matches": matches
        }
    
    async def _rank_experiences(self, profile_experiences: List[ProfileExperience], 
                              job_skills: List[Dict[str, Any]],
                              job_level: str) -> List[Dict[str, Any]]:
        """Rank user experiences by relevance to job.
        
        Args:
            profile_experiences: List of user's experiences
            job_skills: List of job required skills
            job_level: Job level/seniority
            
        Returns:
            List of experiences with relevance scores
        """
        if not profile_experiences:
            return []
        
        ranked_experiences = []
        
        # Get skill names for easier matching
        skill_names = [skill["name"].lower() for skill in job_skills]
        skill_relevance = {skill["name"].lower(): skill.get("relevance", 5) for skill in job_skills}
        
        for exp in profile_experiences:
            # Base relevance score starts at 1
            relevance_score = 1.0
            matching_skills = []
            
            # Check title for relevance
            title_lower = exp.title.lower()
            for skill in skill_names:
                if skill in title_lower:
                    relevance_score += 0.5 * (skill_relevance[skill] / 10)
                    matching_skills.append(skill)
            
            # Check description for relevance
            if exp.description:
                description_lower = exp.description.lower()
                for skill in skill_names:
                    if skill in description_lower and skill not in matching_skills:
                        relevance_score += 0.3 * (skill_relevance[skill] / 10)
                        matching_skills.append(skill)
            
            # Check skills used
            for used_skill in exp.skills_used:
                used_skill_lower = used_skill.lower()
                for skill in skill_names:
                    if skill in used_skill_lower and skill not in matching_skills:
                        relevance_score += 0.2 * (skill_relevance[skill] / 10)
                        matching_skills.append(skill)
            
            # Calculate duration for recency factor
            start_date = datetime.strptime(exp.start_date, "%Y-%m")
            
            if exp.end_date:
                end_date = datetime.strptime(exp.end_date, "%Y-%m")
                is_current = False
            else:
                end_date = datetime.now()
                is_current = True
            
            duration_years = (end_date.year - start_date.year) + (end_date.month - start_date.month) / 12
            
            # Apply recency boost (more recent experience gets higher score)
            years_ago = (datetime.now() - end_date).days / 365
            recency_factor = max(1.0 - (years_ago / 10), 0.5)  # Reduce score for older experience, but no less than 0.5
            
            # Apply current job boost
            current_job_boost = 1.2 if is_current else 1.0
            
            # Apply job level considerations
            if job_level == "executive" and ("director" in title_lower or "head" in title_lower or "chief" in title_lower):
                level_boost = 1.5
            elif job_level == "senior" and ("senior" in title_lower or "lead" in title_lower):
                level_boost = 1.3
            elif job_level == "mid" and not any(junior in title_lower for junior in ["junior", "entry", "intern"]):
                level_boost = 1.2
            elif job_level == "entry" and any(junior in title_lower for junior in ["junior", "entry", "intern"]):
                level_boost = 1.3
            else:
                level_boost = 1.0
            
            # Calculate final relevance score
            final_score = relevance_score * recency_factor * current_job_boost * level_boost
            
            ranked_experiences.append({
                "title": exp.title,
                "company": exp.company,
                "duration": f"{round(duration_years, 1)} years",
                "relevance_score": round(final_score, 2),
                "matching_skills": matching_skills,
                "is_current": is_current
            })
        
        # Sort by relevance score descending
        return sorted(ranked_experiences, key=lambda x: x["relevance_score"], reverse=True)
    
    def _determine_fit_category(self, overall_score: float) -> str:
        """Determine fit category based on overall score.
        
        Args:
            overall_score: Overall match score (0-100)
            
        Returns:
            Fit category string
        """
        if overall_score >= 85:
            return "excellent"
        elif overall_score >= 70:
            return "good"
        elif overall_score >= 50:
            return "fair"
        else:
            return "poor"