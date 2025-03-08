# app/services/resume_builder/template.py

import logging
import os
import yaml
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

class ResumeTemplate:
    """Resume template manager for resume generation."""
    
    def __init__(self, template_name: Optional[str] = None):
        """Initialize resume template.
        
        Args:
            template_name: Name of template to use. If None, uses default template.
        """
        self.template_name = template_name or settings.STORAGE.DEFAULT_TEMPLATE
        self.template_dir = settings.STORAGE.TEMPLATE_DIR
        self.template_data = self._load_template()
    
    def _load_template(self) -> Dict[str, Any]:
        """Load template data from YAML file.
        
        Returns:
            Template configuration as dictionary
        """
        template_path = Path(self.template_dir) / self.template_name
        
        try:
            with open(template_path, 'r') as file:
                template_data = yaml.safe_load(file)
                
            if not isinstance(template_data, dict):
                logger.error(f"Invalid template format: {self.template_name}")
                # Load default template as fallback
                default_template_path = Path(self.template_dir) / "standard.yaml"
                with open(default_template_path, 'r') as file:
                    template_data = yaml.safe_load(file)
            
            return template_data
        except Exception as e:
            logger.error(f"Error loading template {self.template_name}: {str(e)}")
            # Return minimal default template
            return {
                "name": "Standard",
                "sections": [
                    {"name": "header", "title": "Contact Information", "order": 1},
                    {"name": "summary", "title": "Professional Summary", "order": 2},
                    {"name": "experience", "title": "Professional Experience", "order": 3},
                    {"name": "education", "title": "Education", "order": 4},
                    {"name": "skills", "title": "Skills", "order": 5}
                ],
                "fonts": {
                    "main": "Arial",
                    "header": "Arial",
                    "section": "Arial Bold"
                },
                "formatting": {
                    "margins": {"top": 1, "bottom": 1, "left": 1, "right": 1},
                    "line_spacing": 1.15
                }
            }
    
    def get_section_order(self) -> List[str]:
        """Get ordered list of section names.
        
        Returns:
            List of section names in display order
        """
        sections = self.template_data.get("sections", [])
        return [section["name"] for section in sorted(sections, key=lambda x: x.get("order", 999))]
    
    def get_section_title(self, section_name: str) -> str:
        """Get display title for a section.
        
        Args:
            section_name: Internal section name
            
        Returns:
            Display title for section
        """
        sections = self.template_data.get("sections", [])
        for section in sections:
            if section["name"] == section_name:
                return section.get("title", section_name.title())
        
        # Return capitalized section name if not found
        return section_name.title()
    
    def get_formatting(self) -> Dict[str, Any]:
        """Get formatting options for the template.
        
        Returns:
            Dictionary of formatting options
        """
        return self.template_data.get("formatting", {})
    
    def get_fonts(self) -> Dict[str, str]:
        """Get font settings for the template.
        
        Returns:
            Dictionary of font settings
        """
        return self.template_data.get("fonts", {})
    
    def get_layout(self) -> str:
        """Get layout type for the template.
        
        Returns:
            Layout type (e.g., 'standard', 'modern', 'compact')
        """
        return self.template_data.get("layout", "standard")
    
    def get_color_scheme(self) -> Dict[str, str]:
        """Get color scheme for the template.
        
        Returns:
            Dictionary of color settings
        """
        return self.template_data.get("colors", {})