# app/core/exceptions.py
"""Application exceptions."""

class ApplicationError(Exception):
    """Base application exception."""
    pass

class DatabaseError(ApplicationError):
    """Database operation exception."""
    pass

class ScraperError(ApplicationError):
    """Job scraper exception."""
    pass

class LLMError(ApplicationError):
    """LLM service exception."""
    pass

class ResumeBuilderError(ApplicationError):
    """Resume builder exception."""
    pass

class BrowserError(ApplicationError):
    """Browser automation exception."""
    pass

class ConfigurationError(ApplicationError):
    """Configuration exception."""
    pass