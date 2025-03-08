# app/services/job_scraper/indeed.py
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

class IndeedScraper(BaseScraper):
    """Scraper for Indeed jobs."""
    
    BASE_URL = "https://www.indeed.com"
    API_URL = "https://apis.indeed.com/graphql"
    API_HEADERS = {
        "Host": "apis.indeed.com",
        "content-type": "application/json",
        "indeed-api-key": "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8",
        "accept": "application/json",
        "indeed-locale": "en-US",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1",
        "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
    }
    SOURCE_NAME = "indeed"
    JOB_SEARCH_QUERY = """
    query GetJobData {{
        jobSearch(
        {what}
        {location}
        limit: 100
        {cursor}
        sort: RELEVANCE
        {filters}
        ) {{
        pageInfo {{
            nextCursor
        }}
        results {{
            trackingKey
            job {{
            source {{
                name
            }}
            key
            title
            datePublished
            dateOnIndeed
            description {{
                html
            }}
            location {{
                countryName
                countryCode
                admin1Code
                city
                postalCode
                streetAddress
                formatted {{
                short
                long
                }}
            }}
            compensation {{
                estimated {{
                currencyCode
                baseSalary {{
                    unitOfWork
                    range {{
                    ... on Range {{
                        min
                        max
                    }}
                    }}
                }}
                }}
                baseSalary {{
                unitOfWork
                range {{
                    ... on Range {{
                    min
                    max
                    }}
                }}
                }}
                currencyCode
            }}
            attributes {{
                key
                label
            }}
            employer {{
                relativeCompanyPageUrl
                name
                dossier {{
                    employerDetails {{
                    addresses
                    industry
                    employeesLocalizedLabel
                    revenueLocalizedLabel
                    briefDescription
                    ceoName
                    ceoPhotoUrl
                    }}
                    images {{
                        headerImageUrl
                        squareLogoUrl
                    }}
                    links {{
                    corporateWebsite
                }}
                }}
            }}
            recruit {{
                viewJobUrl
                detailedSalary
                workSchedule
            }}
            }}
        }}
        }}
    }}
    """
    
    async def setup_session(self):
        """Set up HTTP session for Indeed requests."""
        if self.session:
            await self.close_session()
        
        # Create proxy manager if using proxies
        self.proxy_manager = ProxyManager(self.proxies) if self.use_proxies else None
        
        # Create session
        self.session = aiohttp.ClientSession(headers=self.API_HEADERS)
    
    async def search_jobs(self, 
                    search_term: str, 
                    location: Optional[str] = None,
                    job_type: Optional[JobType] = None,
                    max_results: int = 20,
                    remote_only: bool = False,
                    **kwargs) -> List[JobPost]:
        """Search for jobs on Indeed."""
        if not self.session:
            await self.setup_session()
        
        jobs: List[JobPost] = []
        cursor = None
        
        try:
            # Build query parameters
            what_param = f'what: "{search_term}"' if search_term else ""
            location_param = ""
            if location:
                location_param = f'location: {{where: "{location}", radius: {kwargs.get("distance", 50)}, radiusUnit: MILES}}'
            
            # Build filters
            filters = []
            
            # Add job type filter
            if job_type:
                job_type_mapping = {
                    JobType.FULL_TIME: "CF3CP",
                    JobType.PART_TIME: "75GKK",
                    JobType.CONTRACT: "NJXCK",
                    JobType.INTERNSHIP: "VDTG7",
                }
                if job_type in job_type_mapping:
                    filters.append(job_type_mapping[job_type])
            
            # Add remote filter
            if remote_only:
                filters.append("DSQF7")
            
            # Format filters for query
            filters_param = ""
            if filters:
                filters_str = '", "'.join(filters)
                filters_param = f"""
                filters: {{
                  composite: {{
                    filters: [{{
                      keyword: {{
                        field: "attributes",
                        keys: ["{filters_str}"]
                      }}
                    }}]
                  }}
                }}
                """
            
            # Set hours old filter if specified
            hours_old = kwargs.get("hours_old")
            if hours_old:
                filters_param = f"""
                filters: {{
                    date: {{
                      field: "dateOnIndeed",
                      start: "{hours_old}h"
                    }}
                }}
                """
            
            while len(jobs) < max_results:
                # Format cursor parameter
                cursor_param = f'cursor: "{cursor}"' if cursor else ""
                
                # Format final query
                query = self.JOB_SEARCH_QUERY.format(
                    what=what_param,
                    location=location_param,
                    cursor=cursor_param,
                    filters=filters_param
                )
                
                # Prepare request payload
                payload = {"query": query}
                
                # Get proxy if enabled
                proxy = None
                if self.proxy_manager:
                    proxy = self.proxy_manager.get_next_proxy()
                
                # Make request with retries
                for attempt in range(self.retry_count):
                    try:
                        async with self.session.post(
                            self.API_URL,
                            json=payload,
                            proxy=proxy["http"] if proxy else None,
                            timeout=self.timeout
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                break
                            elif response.status == 429:
                                logger.warning(f"Rate limited by Indeed. Attempt {attempt+1}/{self.retry_count}")
                                if attempt < self.retry_count - 1:
                                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                                    if self.proxy_manager:
                                        proxy = self.proxy_manager.get_next_proxy()
                                    continue
                                raise ScraperError(f"Rate limited by Indeed after {self.retry_count} attempts")
                            else:
                                logger.warning(f"Indeed API returned status {response.status}. Attempt {attempt+1}/{self.retry_count}")
                                if attempt < self.retry_count - 1:
                                    await asyncio.sleep(self.retry_delay)
                                    continue
                                raise ScraperError(f"Indeed API returned status {response.status}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Request to Indeed timed out. Attempt {attempt+1}/{self.retry_count}")
                        if attempt < self.retry_count - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise ScraperError(f"Request to Indeed timed out after {self.retry_count} attempts")
                
                # Process job results
                job_search_data = data.get("data", {}).get("jobSearch", {})
                job_results = job_search_data.get("results", [])
                
                if not job_results:
                    break
                
                # Process each job
                for job_result in job_results:
                    # Skip if we have enough jobs
                    if len(jobs) >= max_results:
                        break
                    
                    try:
                        job_data = job_result.get("job", {})
                        
                        # Get job ID
                        job_key = job_data.get("key")
                        if not job_key:
                            continue
                        
                        # Get basic job info
                        title = job_data.get("title", "")
                        
                        # Get employer info
                        employer = job_data.get("employer", {})
                        company_name = employer.get("name", "")
                        
                        # Get location
                        location_data = job_data.get("location", {})
                        city = location_data.get("city")
                        state = location_data.get("admin1Code")
                        country_code = location_data.get("countryCode")
                        
                        # Get description
                        description_data = job_data.get("description", {})
                        description_html = description_data.get("html", "")
                        # Convert HTML to plain text for description
                        soup = BeautifulSoup(description_html, "html.parser")
                        description = soup.get_text(separator="\n").strip()
                        
                        # Get date posted
                        date_published = job_data.get("datePublished")
                        date_posted = None
                        if date_published:
                            date_posted = datetime.fromtimestamp(date_published / 1000)
                        
                        # Get compensation
                        compensation_data = job_data.get("compensation", {})
                        compensation = self._parse_compensation(compensation_data)
                        
                        # Get job type from attributes
                        attributes = job_data.get("attributes", [])
                        job_types = self._parse_job_type(attributes)
                        
                        # Get job URL
                        job_url = f"{self.BASE_URL}/viewjob?jk={job_key}"
                        
                        # Get direct job URL if available
                        recruit_data = job_data.get("recruit", {})
                        job_url_direct = recruit_data.get("viewJobUrl")
                        
                        # Check if remote
                        is_remote = self._is_remote(job_data, description)
                        
                        # Get employer details
                        employer_dossier = employer.get("dossier", {})
                        employer_details = employer_dossier.get("employerDetails", {})
                        employer_images = employer_dossier.get("images", {})
                        employer_links = employer_dossier.get("links", {})
                        
                        company_industry = employer_details.get("industry", "").replace("Iv1", "").replace("_", " ").title().strip() if employer_details.get("industry") else None
                        company_logo = employer_images.get("squareLogoUrl")
                        company_url = employer_links.get("corporateWebsite")
                        
                        # Create job post object
                        job_post = JobPost(
                            id=f"in-{job_key}",
                            source=self.SOURCE_NAME,
                            title=title,
                            company_name=company_name,
                            location=Location(city=city, state=state, country=country_code),
                            job_url=job_url,
                            job_url_direct=job_url_direct,
                            description=description,
                            job_type=job_types,
                            compensation=compensation,
                            date_posted=date_posted,
                            is_remote=is_remote,
                            date_scraped=datetime.utcnow(),
                            emails=self._extract_emails(description),
                            status="new"
                        )
                        
                        jobs.append(job_post)
                    except Exception as e:
                        logger.warning(f"Error processing Indeed job: {str(e)}")
                
                # Get next cursor
                page_info = job_search_data.get("pageInfo", {})
                cursor = page_info.get("nextCursor")
                
                # Break if no more pages
                if not cursor:
                    break
        
        except ScraperError:
            # Re-raise scraper errors
            raise
        except Exception as e:
            logger.error(f"Error searching Indeed jobs: {str(e)}")
            raise ScraperError(f"Error searching Indeed jobs: {str(e)}")
        
        return jobs[:max_results]
    
    async def get_job_details(self, job_url: str) -> Dict[str, Any]:
        """Get detailed job information from Indeed."""
        if not self.session:
            await self.setup_session()
        
        job_key = None
        
        # Extract job key from URL or use directly
        if job_url.startswith(self.BASE_URL):
            parsed_url = urlparse(job_url)
            query_params = parse_qs(parsed_url.query)
            job_key = query_params.get("jk", [None])[0]
        else:
            job_key = job_url  # Assume job_url is the job key if not a full URL
        
        if not job_key:
            raise ScraperError(f"Invalid Indeed job URL or key: {job_url}")
        
        try:
            # Format query for single job
            query = f"""
            query GetJobViewData {{
                jobView(
                    key: "{job_key}"
                ) {{
                    job {{
                        key
                        title
                        description {{
                            html
                        }}
                        employmentTypes
                        compensationInfo {{
                            salary {{
                                min
                                max
                                currencyCode
                                unitOfWork
                            }}
                        }}
                        remoteAllowed
                        requirements {{
                            yearsOfExperience {{
                                min
                                max
                            }}
                            education {{
                                required
                                preferredLevel
                            }}
                            languageRequirements {{
                                language
                                proficiencyRequired
                            }}
                        }}
                    }}
                    employer {{
                        name
                        relativeCompanyUrl
                        dossier {{
                            employerDetails {{
                                shortDescription
                                overview
                                industry
                                employeesLocalizedLabel
                                revenueLocalizedLabel
                            }}
                            links {{
                                corporateWebsite
                            }}
                            images {{
                                squareLogoUrl
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            # Prepare payload
            payload = {"query": query}
            
            # Get proxy if enabled
            proxy = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_next_proxy()
            
            # Make request with retries
            for attempt in range(self.retry_count):
                try:
                    async with self.session.post(
                        self.API_URL,
                        json=payload,
                        proxy=proxy["http"] if proxy else None,
                        timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            break
                        elif response.status == 429:
                            logger.warning(f"Rate limited by Indeed. Attempt {attempt+1}/{self.retry_count}")
                            if attempt < self.retry_count - 1:
                                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                                if self.proxy_manager:
                                    proxy = self.proxy_manager.get_next_proxy()
                                continue
                            raise ScraperError(f"Rate limited by Indeed after {self.retry_count} attempts")
                        else:
                            logger.warning(f"Indeed API returned status {response.status}. Attempt {attempt+1}/{self.retry_count}")
                            if attempt < self.retry_count - 1:
                                await asyncio.sleep(self.retry_delay)
                                continue
                            raise ScraperError(f"Indeed API returned status {response.status}")
                except asyncio.TimeoutError:
                    logger.warning(f"Request to Indeed timed out. Attempt {attempt+1}/{self.retry_count}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    raise ScraperError(f"Request to Indeed timed out after {self.retry_count} attempts")
            
            # Process job data
            job_view = data.get("data", {}).get("jobView", {})
            job_data = job_view.get("job", {})
            employer_data = job_view.get("employer", {})
            
            if not job_data:
                raise ScraperError(f"No job data found for Indeed job key: {job_key}")
            
            # Extract job details
            title = job_data.get("title", "")
            
            # Extract description
            description_data = job_data.get("description", {})
            description_html = description_data.get("html", "")
            soup = BeautifulSoup(description_html, "html.parser")
            description = soup.get_text(separator="\n").strip()
            
            # Extract job types
            employment_types = job_data.get("employmentTypes", [])
            job_types = []
            for employment_type in employment_types:
                for jt in JobType:
                    if employment_type.lower() in jt.value:
                        job_types.append(jt)
                        break
            
            # Extract compensation
            compensation_info = job_data.get("compensationInfo", {})
            salary_data = compensation_info.get("salary", {})
            compensation = None
            if salary_data:
                min_amount = salary_data.get("min")
                max_amount = salary_data.get("max")
                currency = salary_data.get("currencyCode", "USD")
                unit_of_work = salary_data.get("unitOfWork", "")
                
                interval = CompensationInterval.YEARLY
                if unit_of_work:
                    if unit_of_work.upper() == "HOUR":
                        interval = CompensationInterval.HOURLY
                    elif unit_of_work.upper() == "DAY":
                        interval = CompensationInterval.DAILY
                    elif unit_of_work.upper() == "WEEK":
                        interval = CompensationInterval.WEEKLY
                    elif unit_of_work.upper() == "MONTH":
                        interval = CompensationInterval.MONTHLY
                
                if min_amount or max_amount:
                    compensation = Compensation(
                        interval=interval,
                        min_amount=min_amount,
                        max_amount=max_amount,
                        currency=currency
                    )
            
            # Extract requirements
            requirements = job_data.get("requirements", {})
            years_experience = requirements.get("yearsOfExperience", {})
            min_experience = years_experience.get("min")
            max_experience = years_experience.get("max")
            
            education = requirements.get("education", {})
            education_required = education.get("required", False)
            education_level = education.get("preferredLevel", "")
            
            # Extract company information
            company_name = employer_data.get("name", "")
            company_url = employer_data.get("dossier", {}).get("links", {}).get("corporateWebsite")
            company_logo = employer_data.get("dossier", {}).get("images", {}).get("squareLogoUrl")
            company_industry = employer_data.get("dossier", {}).get("employerDetails", {}).get("industry", "")
            
            if company_industry:
                company_industry = company_industry.replace("Iv1", "").replace("_", " ").title().strip()
            
            # Create detailed job info
            job_details = {
                "id": f"in-{job_key}",
                "title": title,
                "company_name": company_name,
                "description": description,
                "job_type": job_types if job_types else None,
                "compensation": compensation,
                "job_url": f"{self.BASE_URL}/viewjob?jk={job_key}",
                "is_remote": job_data.get("remoteAllowed", False),
                "emails": self._extract_emails(description),
                "min_experience": min_experience,
                "max_experience": max_experience,
                "education_required": education_required,
                "education_level": education_level,
                "company_url": company_url,
                "company_logo": company_logo,
                "company_industry": company_industry
            }
            
            return job_details
        
        except ScraperError:
            # Re-raise scraper errors
            raise
        except Exception as e:
            logger.error(f"Error getting Indeed job details: {str(e)}")
            raise ScraperError(f"Error getting Indeed job details: {str(e)}")
    
    def _parse_compensation(self, compensation_data: Dict[str, Any]) -> Optional[Compensation]:
        """Parse compensation from Indeed API data.
        
        Args:
            compensation_data: Compensation data from Indeed API
            
        Returns:
            Compensation object or None if parsing fails
        """
        try:
            base_salary = compensation_data.get("baseSalary")
            estimated = compensation_data.get("estimated")
            
            # Try to use direct data first, then estimated
            salary_data = base_salary if base_salary else (estimated.get("baseSalary") if estimated else None)
            if not salary_data:
                return None
            
            # Get unit of work (interval)
            unit_of_work = salary_data.get("unitOfWork", "").upper()
            interval = CompensationInterval.YEARLY
            if unit_of_work == "DAY":
                interval = CompensationInterval.DAILY
            elif unit_of_work == "HOUR":
                interval = CompensationInterval.HOURLY
            elif unit_of_work == "WEEK":
                interval = CompensationInterval.WEEKLY
            elif unit_of_work == "MONTH":
                interval = CompensationInterval.MONTHLY
            
            # Get salary range
            range_data = salary_data.get("range", {})
            min_amount = range_data.get("min")
            max_amount = range_data.get("max")
            
            # Get currency
            currency = compensation_data.get("currencyCode", "USD")
            if estimated and not currency:
                currency = estimated.get("currencyCode", "USD")
            
            if min_amount is not None or max_amount is not None:
                return Compensation(
                    interval=interval,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    currency=currency
                )
            
            return None
        except Exception as e:
            logger.warning(f"Error parsing Indeed compensation: {str(e)}")
            return None
    
    def _parse_job_type(self, attributes: List[Dict[str, str]]) -> List[JobType]:
        """Parse job type from Indeed job attributes.
        
        Args:
            attributes: List of attribute dictionaries
            
        Returns:
            List of JobType enums
        """
        job_types = []
        
        for attr in attributes:
            attr_key = attr.get("key", "")
            attr_label = attr.get("label", "").lower().replace("-", "").replace(" ", "")
            
            for jt in JobType:
                if attr_label in jt.value:
                    job_types.append(jt)
                    break
        
        return job_types if job_types else None
    
    def _is_remote(self, job_data: Dict[str, Any], description: str) -> bool:
        """Check if job is remote based on job data and description.
        
        Args:
            job_data: Job data dictionary
            description: Job description text
            
        Returns:
            True if job is remote, False otherwise
        """
        # Check attributes
        attributes = job_data.get("attributes", [])
        for attr in attributes:
            if "remote" in attr.get("label", "").lower():
                return True
        
        # Check location
        location = job_data.get("location", {})
        formatted = location.get("formatted", {})
        location_text = formatted.get("long", "")
        if "remote" in location_text.lower():
            return True
        
        # Check description
        remote_keywords = ["remote", "work from home", "wfh"]
        for keyword in remote_keywords:
            if keyword in description.lower():
                return True
        
        return False
    
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