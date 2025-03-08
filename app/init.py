# app/__init__.py
"""Main application package."""
from app.config import settings
from app.core.logging import logger

__version__ = settings.APP_VERSION

# Log application startup
logger.info(f"Starting {settings.APP_NAME} v{__version__} in {settings.ENVIRONMENT} environment")

# Initialize components on import
def init_app():
    """Initialize application components."""
    from app.db.mongodb import mongodb
    
    # Log initialization
    logger.info("Initializing application components")
    
    # Return initialized components
    return {
        "mongodb": mongodb
    }

# Initialize application components
app_components = init_app()