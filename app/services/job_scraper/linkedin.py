# app/services/job_scraper/linkedin.py
import aiohttp
import asyncio
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

from app.services.job_scraper.base import BaseScraper
from app.core.models import JobPost, JobType, Location, Compensation, CompensationInterval
from app.core.logging import logger
from app.core.exceptions import ScraperError
from app.utils.proxies import ProxyManager

class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn jobs."""
    
    BASE_URL = "https://www.linkedin.com"
    API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    JOBS_PER_PAGE = 25
    SOURCE_NAME = "linkedin"
    
    async def setup_session(self):
        """Set up HTTP session for LinkedIn requests."""
        if self.session:
            await self.close_session()
        
        # Create proxy manager if using proxies
        self.proxy_manager = ProxyManager(self.proxies) if self.use_proxies else None
        
        # Create session
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        })
    
    async def search_jobs(self, 
                    search_term: str, 
                    location: Optional[str] = None,
                    job_type: Optional[JobType] = None,
                    max_results: int = 20,
                    remote_only: bool = False,
                    **kwargs) -> List[JobPost]:
        """Search for jobs on LinkedIn."""
        if not self.session:
            await self.setup_session()
        
        jobs: List[JobPost] = []
        start = kwargs.get("offset", 0)
        seen_job_ids = set()
        
        # Map job type to LinkedIn's format
        job_type_code = None
        if job_type:
            job_type_mapping = {
                JobType.FULL_TIME: "F",
                JobType.PART_TIME: "P",
                JobType.CONTRACT: "C",
                JobType.TEMPORARY: "T",
                JobType.INTERNSHIP: "I"
            }
            job_type_code = job_type_mapping.get(job_type)
        
        # Calculate max pages needed
        max_pages = (max_results + self.JOBS_PER_PAGE - 1) // self.JOBS_PER_PAGE
        
        for page in range(max_pages):
            if len(jobs) >= max_results:
                break
            
            current_start = start + (page * self.JOBS_PER_PAGE)
            
            try:
                params = {
                    "keywords": search_term,
                    "location": location,
                    "f_WT": 2 if remote_only else None,  # 2 is remote
                    "f_JT": job_type_code,
                    "start": current_start,
                    "pageNum": 0,  # Always 0 since we're using start param
                }
                
                # Add any extra parameters from kwargs
                for k, v in kwargs.items():
                    if k not in params and v is not None:
                        params[k] = v
                
                # Remove None parameters
                params = {k: v for k, v in params.items() if v is not None}
                
                # Rotate proxy if enabled
                proxy = None
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_next_proxy()
                
                # Make request with retries
                for attempt in range(self.retry_count):
                    try:
                        async with self.session.get(
                            self.API_URL,
                            params=params,
                            proxy=proxy["http"] if proxy else None,
                            timeout=self.timeout
                        ) as response:
                            if response.status == 200:
                                html = await response.text()
                                break
                            elif response.status == 429:
                                logger.warning(f"Rate limited by LinkedIn. Attempt {attempt+1}/{self.retry_count}")
                                if attempt < self.retry_count - 1:
                                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                                    if self.proxy_manager:
                                        proxy = self.proxy_manager.get_next_proxy()
                                    continue
                                raise ScraperError(f"Rate limited by LinkedIn after {self.retry_count} attempts")
                            else:
                                logger.warning(f"LinkedIn API returned status {response.status}. Attempt {attempt+1}/{self.retry_count}")
                                if attempt < self.retry_count - 1:
                                    await asyncio.sleep(self.retry_delay)
                                    continue
                                raise ScraperError(f"LinkedIn API returned status {response.status}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Request to LinkedIn timed out. Attempt {attempt+1}/{self.retry_count}")
                        if attempt < self.retry_count - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise ScraperError(f"Request to LinkedIn timed out after {self.retry_count} attempts")
                
                # Parse job listings from HTML
                soup = BeautifulSoup(html, "html.parser")
                job_cards = soup.find_all("div", class_="base-card")
                
                if not job_cards:
                    logger.info(f"No more job listings found at offset {current_start}")
                    break
                
                # Extract job data from cards
                for job_card in job_cards:
                    # Skip if we have enough jobs
                    if len(jobs) >= max_results:
                        break
                    
                    try:
                        # Extract job link and ID
                        job_link_elem = job_card.find("a", class_="base-card__full-link")
                        if not job_link_elem:
                            continue
                        
                        job_url = job_link_elem.get("href", "").split("?")[0]
                        job_id = job_url.split("-")[-1]
                        
                        # Skip if we've seen this job before
                        if job_id in seen_job_ids:
                            continue
                        seen_job_ids.add(job_id)
                        
                        # Extract basic job info
                        title_elem = job_card.find("span", class_="sr-only")
                        title = title_elem.text.strip() if title_elem else ""
                        
                        company_elem = job_card.find("h4", class_="base-search-card__subtitle")
                        company_link = company_elem.find("a") if company_elem else None
                        company_name = company_link.text.strip() if company_link else ""
                        
                        # Extract location
                        location_elem = job_card.find("span", class_="job-search-card__location")
                        location_text = location_elem.text.strip() if location_elem else ""
                        
                        city = state = country = None
                        if location_text:
                            location_parts = location_text.split(", ")
                            if len(location_parts) == 2:
                                city, state = location_parts
                            elif len(location_parts) == 3:
                                city, state, country = location_parts
                            else:
                                city = location_text
                        
                        # Extract posted date
                        date_elem = job_card.find("time", class_="job-search-card__listdate")
                        date_posted = None
                        if date_elem and "datetime" in date_elem.attrs:
                            date_str = date_elem["datetime"]
                            try:
                                date_posted = datetime.fromisoformat(date_str)
                            except ValueError:
                                pass
                        
                        # Extract salary if available
                        salary_elem = job_card.find("span", class_="job-search-card__salary-info")
                        compensation = None
                        if salary_elem:
                            salary_text = salary_elem.text.strip()
                            compensation = self._parse_compensation(salary_text)
                        
                        # Create job post object
                        job_post = JobPost(
                            id=f"li-{job_id}",
                            source=self.SOURCE_NAME,
                            title=title,
                            company_name=company_name,
                            location=Location(city=city, state=state, country=country),
                            job_url=f"{self.BASE_URL}/jobs/view/{job_id}",
                            date_posted=date_posted,
                            compensation=compensation,
                            date_scraped=datetime.utcnow(),
                            status="new"
                        )
                        
                        jobs.append(job_post)
                    except Exception as e:
                        logger.warning(f"Error processing LinkedIn job card: {str(e)}")
            
            except ScraperError as e:
                # Re-raise scraper errors
                raise
            except Exception as e:
                logger.error(f"Error searching LinkedIn jobs: {str(e)}")
                raise ScraperError(f"Error searching LinkedIn jobs: {str(e)}")
        
        return jobs[:max_results]
    
    async def get_job_details(self, job_url: str) -> Dict[str, Any]:
        """Get detailed job information from LinkedIn."""
        if not self.session:
            await self.setup_session()
        
        if not job_url.startswith(self.BASE_URL):
            job_id = job_url  # Assume job_url is the job ID if not a full URL
            job_url = f"{self.BASE_URL}/jobs/view/{job_id}"
        else:
            # Extract job ID from URL
            job_id = job_url.split("/")[-1]
            if "?" in job_id:
                job_id = job_id.split("?")[0]
        
        try:
            # Rotate proxy if enabled
            proxy = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_next_proxy()
            
            # Make request with retries
            html = None
            for attempt in range(self.retry_count):
                try:
                    async with self.session.get(
                        job_url,
                        proxy=proxy["http"] if proxy else None,
                        timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            break
                        elif response.status == 429:
                            logger.warning(f"Rate limited by LinkedIn. Attempt {attempt+1}/{self.retry_count}")
                            if attempt < self.retry_count - 1:
                                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                                if self.proxy_manager:
                                    proxy = self.proxy_manager.get_next_proxy()
                                continue
                            raise ScraperError(f"Rate limited by LinkedIn after {self.retry_count} attempts")
                        else:
                            logger.warning(f"LinkedIn returned status {response.status}. Attempt {attempt+1}/{self.retry_count}")
                            if attempt < self.retry_count - 1:
                                await asyncio.sleep(self.retry_delay)
                                continue
                            raise ScraperError(f"LinkedIn returned status {response.status}")
                except asyncio.TimeoutError:
                    logger.warning(f"Request to LinkedIn timed out. Attempt {attempt+1}/{self.retry_count}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    raise ScraperError(f"Request to LinkedIn timed out after {self.retry_count} attempts")
            
            if not html:
                raise ScraperError(f"Failed to retrieve LinkedIn job details for {job_id}")
            
            # Parse job details from HTML
            soup = BeautifulSoup(html, "html.parser")
            
            # Check if we're redirected to signup page
            if "linkedin.com/signup" in response.url:
                raise ScraperError("LinkedIn is requiring sign-in to view job details")
            
            # Extract job description
            description_div = soup.find("div", {"class": lambda c: c and "show-more-less-html__markup" in c})
            description = description_div.get_text(separator="\n").strip() if description_div else None
            
            # Extract job type
            job_type = None
            job_type_section = soup.find("h3", string=lambda s: s and "Employment type" in s)
            if job_type_section:
                job_type_span = job_type_section.find_next("span", class_="description__job-criteria-text")
                if job_type_span:
                    job_type_text = job_type_span.text.strip().lower().replace("-", "")
                    for jt in JobType:
                        if job_type_text in jt.value:
                            job_type = [jt]
                            break
            
            # Extract job level
            job_level = None
            job_level_section = soup.find("h3", string=lambda s: s and "Seniority level" in s)
            if job_level_section:
                job_level_span = job_level_section.find_next("span", class_="description__job-criteria-text")
                if job_level_span:
                    job_level = job_level_span.text.strip().lower()
            
            # Extract company industry
            company_industry = None
            industry_section = soup.find("h3", string=lambda s: s and "Industries" in s)
            if industry_section:
                industry_span = industry_section.find_next("span", class_="description__job-criteria-text")
                if industry_span:
                    company_industry = industry_span.text.strip()
            
            # Extract company logo
            company_logo = None
            logo_img = soup.find("img", {"class": "artdeco-entity-image"})
            if logo_img and "data-delayed-url" in logo_img.attrs:
                company_logo = logo_img["data-delayed-url"]
            
            # Extract direct job URL
            job_url_direct = None
            apply_url_code = soup.find("code", id="applyUrl")
            if apply_url_code:
                url_match = re.search(r'(?<=\?url=)[^"]+', apply_url_code.text)
                if url_match:
                    from urllib.parse import unquote
                    job_url_direct = unquote(url_match.group())
            
            # Return detailed job info
            return {
                "id": f"li-{job_id}",
                "title": soup.find("h1", class_="top-card-layout__title").text.strip() if soup.find("h1", class_="top-card-layout__title") else "",
                "company_name": soup.find("a", class_="topcard__org-name-link").text.strip() if soup.find("a", class_="topcard__org-name-link") else "",
                "description": description,
                "job_type": job_type,
                "job_level": job_level,
                "company_industry": company_industry,
                "company_logo": company_logo,
                "job_url": job_url,
                "job_url_direct": job_url_direct,
                "is_remote": "remote" in html.lower(),
                "emails": self._extract_emails(description) if description else None
            }
        except ScraperError:
            # Re-raise scraper errors
            raise
        except Exception as e:
            logger.error(f"Error getting LinkedIn job details: {str(e)}")
            raise ScraperError(f"Error getting LinkedIn job details: {str(e)}")
    
    def _parse_compensation(self, salary_text: str) -> Optional[Compensation]:
        """Parse compensation from LinkedIn salary text.
        
        Args:
            salary_text: Salary text from LinkedIn
            
        Returns:
            Compensation object or None if parsing fails
        """
        try:
            # Handle different salary formats
            if "hour" in salary_text.lower():
                interval = CompensationInterval.HOURLY
            elif "month" in salary_text.lower():
                interval = CompensationInterval.MONTHLY
            elif "year" in salary_text.lower() or "/yr" in salary_text.lower():
                interval = CompensationInterval.YEARLY
            else:
                interval = CompensationInterval.YEARLY  # Default
            
            # Extract salary range using regex
            currency_symbol = ""
            if "$" in salary_text:
                currency_symbol = "USD"
            elif "€" in salary_text:
                currency_symbol = "EUR"
            elif "£" in salary_text:
                currency_symbol = "GBP"
            
            # Extract min and max values
            values = re.findall(r'[\d,]+\.?\d*', salary_text)
            if len(values) >= 2:
                min_value = float(values[0].replace(",", ""))
                max_value = float(values[1].replace(",", ""))
                return Compensation(
                    interval=interval,
                    min_amount=min_value,
                    max_amount=max_value,
                    currency=currency_symbol or "USD"
                )
            elif len(values) == 1:
                value = float(values[0].replace(",", ""))
                return Compensation(
                    interval=interval,
                    min_amount=value,
                    max_amount=value,
                    currency=currency_symbol or "USD"
                )
            
            return None
        except Exception as e:
            logger.warning(f"Error parsing LinkedIn compensation: {str(e)}")
            return None
    
    @staticmethod
    def _extract_emails(text: str) -> List[str]:
        """Extract email addresses from text.
        
        Args:
            text: Text to extract emails from
            
        Returns:
            List of unique email addresses
        """
        if not text:
            return []
        
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails))  # Return unique emails