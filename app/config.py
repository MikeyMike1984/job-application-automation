# app/config.py
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from pydantic import BaseSettings, Field

# Load environment variables from .env file
load_dotenv()

class LoggingConfig(BaseSettings):
    """Logging configuration."""
    LEVEL: str = Field(default="INFO")
    FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    FILE_PATH: Optional[str] = Field(default=None)

class DatabaseConfig(BaseSettings):
    """Database configuration."""
    URI: str = Field(default="mongodb://localhost:27017")
    NAME: str = Field(default="job_application_system")
    MIN_POOL_SIZE: int = Field(default=5)
    MAX_POOL_SIZE: int = Field(default=10)
    TIMEOUT_MS: int = Field(default=5000)

class LLMConfig(BaseSettings):
    """LLM configuration."""
    PROVIDER: str = Field(default="openai")
    MODEL: str = Field(default="gpt-4o")
    API_KEY: str = Field(default="")
    API_BASE: Optional[str] = Field(default=None)
    MAX_TOKENS: int = Field(default=1000)
    TEMPERATURE: float = Field(default=0.2)
    TIMEOUT_SECONDS: float = Field(default=60.0)

class ScraperConfig(BaseSettings):
    """Job scraper configuration."""
    CONCURRENT_REQUESTS: int = Field(default=5)
    REQUEST_TIMEOUT: float = Field(default=30.0)
    USER_AGENT: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    USE_PROXIES: bool = Field(default=False)
    PROXIES: List[str] = Field(default=[])
    RETRY_COUNT: int = Field(default=3)
    RETRY_DELAY: float = Field(default=1.0)

class BrowserConfig(BaseSettings):
    """Browser automation configuration."""
    HEADLESS: bool = Field(default=True)
    BROWSER_TYPE: str = Field(default="chrome")
    DRIVER_PATH: Optional[str] = Field(default=None)
    WINDOW_WIDTH: int = Field(default=1920)
    WINDOW_HEIGHT: int = Field(default=1080)
    IMPLICIT_WAIT: int = Field(default=10)
    PAGE_LOAD_TIMEOUT: int = Field(default=30)
    CLOSE_ON_COMPLETE: bool = Field(default=True)

class StorageConfig(BaseSettings):
    """File storage configuration."""
    RESUME_DIR: str = Field(default="resumes")
    TEMPLATE_DIR: str = Field(default="templates")
    FONTS_DIR: str = Field(default="templates/fonts")
    DEFAULT_TEMPLATE: str = Field(default="standard.yaml")

class Settings(BaseSettings):
    """Application settings."""
    # Application
    APP_NAME: str = Field(default="Job Application Automation")
    APP_VERSION: str = Field(default="0.1.0")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    SECRET_KEY: str = Field(default="changeme")
    
    # Component configurations
    LOGGING: LoggingConfig = LoggingConfig()
    DATABASE: DatabaseConfig = DatabaseConfig()
    LLM: LLMConfig = LLMConfig()
    SCRAPER: ScraperConfig = ScraperConfig()
    BROWSER: BrowserConfig = BrowserConfig()
    STORAGE: StorageConfig = StorageConfig()
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_nested_delimiter = "__"

def get_settings() -> Settings:
    """Get application settings with environment-specific overrides.
    
    Returns:
        Settings object
    """
    # Create base settings
    settings = Settings()
    
    # Override with environment-specific settings
    env = os.getenv("ENVIRONMENT", "development")
    settings.ENVIRONMENT = env
    
    # Load production settings
    if env == "production":
        settings.DEBUG = False
        settings.BROWSER.HEADLESS = True
    
    # Load development settings
    elif env == "development":
        settings.DEBUG = True
        settings.BROWSER.HEADLESS = False
    
    # Load testing settings
    elif env == "testing":
        settings.DEBUG = True
        settings.DATABASE.NAME = f"{settings.DATABASE.NAME}_test"
        settings.BROWSER.HEADLESS = True
    
    # Load environment-specific variables
    for key, value in os.environ.items():
        if key.startswith("APP_"):
            # Handle nested settings with delimiter
            parts = key.split("__")
            if len(parts) > 1:
                section = parts[0]
                setting = "__".join(parts[1:])
                
                if hasattr(settings, section):
                    section_obj = getattr(settings, section)
                    if hasattr(section_obj, setting):
                        # Convert value to appropriate type
                        current_value = getattr(section_obj, setting)
                        if isinstance(current_value, bool):
                            setattr(section_obj, setting, value.lower() in ("true", "1", "yes"))
                        elif isinstance(current_value, int):
                            setattr(section_obj, setting, int(value))
                        elif isinstance(current_value, float):
                            setattr(section_obj, setting, float(value))
                        elif isinstance(current_value, list):
                            setattr(section_obj, setting, value.split(","))
                        else:
                            setattr(section_obj, setting, value)
    
    return settings

# Create a global settings instance
settings = get_settings()