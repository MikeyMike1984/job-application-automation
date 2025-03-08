# app/services/resume_builder/pdf_generator.py

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    ListFlowable, ListItem, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.config import settings

logger = logging.getLogger(__name__)

# Register fonts
try:
    calibri_path = os.path.join(settings.STORAGE.FONTS_DIR, "calibri.ttf")
    calibri_bold_path = os.path.join(settings.STORAGE.FONTS_DIR, "calibrib.ttf")
    
    if os.path.exists(calibri_path) and os.path.exists(calibri_bold_path):
        pdfmetrics.registerFont(TTFont("Calibri", calibri_path))
        pdfmetrics.registerFont(TTFont("Calibri-Bold", calibri_bold_path))
    else:
        logger.warning("Calibri fonts not found. Using Helvetica instead.")
except Exception as e:
    logger.warning(f"Error registering custom fonts: {str(e)}. Using default fonts.")

class Bullet(Flowable):
    """A custom flowable for a solid circle bullet point."""
    
    def __init__(self, size=4):
        Flowable.__init__(self)
        self.size = size
        self.width = size + 5
        self.height = size
        
    def draw(self):
        self.canv.setFillColor(colors.black)
        self.canv.circle(self.size/2, self.size/2, self.size/2, fill=1)

def is_calibri_available():
    """Check if Calibri font is available."""
    try:
        return "Calibri" in pdfmetrics.getRegisteredFontNames()
    except:
        return False

def create_styles():
    """Create custom paragraph styles for resume."""
    styles = getSampleStyleSheet()
    
    # Determine font family
    font_family = "Calibri" if is_calibri_available() else "Helvetica"
    bold_font = "Calibri-Bold" if is_calibri_available() else "Helvetica-Bold"
    
    # Name style
    styles.add(ParagraphStyle(
        name='Name',
        fontName=bold_font,
        fontSize=14,
        leading=16,
        spaceAfter=0
    ))
    
    # Title style
    styles.add(ParagraphStyle(
        name='Title',
        fontName=bold_font,
        fontSize=11,
        leading=13,
        spaceAfter=6
    ))
    
    # Contact info style
    styles.add(ParagraphStyle(
        name='Contact',
        fontName=font_family,
        fontSize=10,
        leading=12,
        spaceAfter=12
    ))
    
    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName=bold_font,
        fontSize=13,
        leading=15,
        spaceBefore=12,
        spaceAfter=6
    ))
    
    # Normal text style
    styles.add(ParagraphStyle(
        name='NormalText',
        fontName=font_family,
        fontSize=11,
        leading=13,
        spaceAfter=3
    ))
    
    # Bold text style
    styles.add(ParagraphStyle(
        name='BoldText',
        fontName=bold_font,
        fontSize=11,
        leading=13,
        spaceAfter=3
    ))
    
    # Bullet point style
    styles.add(ParagraphStyle(
        name='Bullet',
        fontName=font_family,
        fontSize=11,
        leading=13,
        leftIndent=12,
        firstLineIndent=-12,
        spaceBefore=0,
        spaceAfter=3
    ))
    
    return styles

def generate_resume_pdf(resume_content: Dict[str, Any], output_path: str) -> str:
    """Generate PDF resume from content.
    
    Args:
        resume_content: Dictionary containing resume content sections
        output_path: Path to save the PDF file
        
    Returns:
        Path to the generated PDF file
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=72,  # 1 inch in points
        rightMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Get styles
    styles = create_styles()
    
    # Build content
    elements = []
    
    # Header section
    header = resume_content.get("header", {})
    name = header.get("name", "")
    title = header.get("title", "")
    contact_info = header.get("contact", {})
    
    # Name and title
    elements.append(Paragraph(name, styles["Name"]))
    elements.append(Paragraph(title, styles["Title"]))
    
    # Contact info
    contact_text = []
    if contact_info.get("email"):
        contact_text.append(contact_info["email"])
    if contact_info.get("phone"):
        contact_text.append(contact_info["phone"])
    if contact_info.get("linkedin"):
        contact_text.append(contact_info["linkedin"])
    if contact_info.get("location"):
        contact_text.append(contact_info["location"])
        
    contact_line = " | ".join(contact_text)
    elements.append(Paragraph(contact_line, styles["Contact"]))
    
    # Summary section
    elements.append(Paragraph("Professional Summary", styles["SectionHeader"]))
    summary = resume_content.get("summary", "")
    elements.append(Paragraph(summary, styles["NormalText"]))
    
    # Skills section
    elements.append(Paragraph("Skills", styles["SectionHeader"]))
    skills = resume_content.get("skills", {})
    
    # Create bullet points for skills
    for category, skill_list in skills.items():
        if skill_list:
            # Create skill bullets
            for skill in skill_list:
                bullet_text = f"<bullet>&bull;</bullet> <b>{category.title()}</b>: {skill}"
                elements.append(Paragraph(bullet_text, styles["Bullet"]))
            
    # Experience section
    elements.append(Paragraph("Professional Experience", styles["SectionHeader"]))
    experiences = resume_content.get("experience", [])
    
    for exp in experiences:
        # Company and position
        position = exp.get("title", "")
        company = exp.get("company", "")
        date_range = ""
        
        if exp.get("start_date") and exp.get("end_date"):
            start_date = datetime.strptime(exp["start_date"], "%Y-%m").strftime("%B %Y")
            end_date = datetime.strptime(exp["end_date"], "%Y-%m").strftime("%B %Y")
            date_range = f"{start_date} - {end_date}"
        elif exp.get("start_date"):
            start_date = datetime.strptime(exp["start_date"], "%Y-%m").strftime("%B %Y")
            date_range = f"{start_date} - Present"
            
        position_line = f"<b>{position}</b>"
        elements.append(Paragraph(position_line, styles["BoldText"]))
        elements.append(Paragraph(f"<b>{date_range}</b>", styles["BoldText"]))
        elements.append(Paragraph(company, styles["NormalText"]))
        
        # Achievements
        achievements = exp.get("achievements", [])
        for achievement in achievements:
            bullet_text = f"<bullet>&bull;</bullet> {achievement}"
            elements.append(Paragraph(bullet_text, styles["Bullet"]))
        
        elements.append(Spacer(1, 0.1*inch))
    
    # Education section
    elements.append(Paragraph("Education", styles["SectionHeader"]))
    education = resume_content.get("education", [])
    
    for edu in education:
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        institution = edu.get("institution", "")
        location = edu.get("location", "")
        graduation = edu.get("graduation_date", "")
        
        education_line = f"<b>{degree} in {field}</b>"
        elements.append(Paragraph(education_line, styles["BoldText"]))
        
        institution_line = f"{institution}, {location} | {graduation}"
        elements.append(Paragraph(institution_line, styles["NormalText"]))
    
    # Certifications section
    certifications = resume_content.get("certifications", [])
    if certifications:
        elements.append(Paragraph("Certifications", styles["SectionHeader"]))
        
        for cert in certifications:
            cert_name = cert.get("name", "")
            cert_issuer = cert.get("issuer", "")
            cert_date = cert.get("date", "")
            
            cert_text = f"<bullet>&bull;</bullet> {cert_name}"
            if cert_issuer:
                cert_text += f" - {cert_issuer}"
            if cert_date:
                try:
                    cert_date_formatted = datetime.strptime(cert_date, "%Y-%m").strftime("%B %Y")
                    cert_text += f" ({cert_date_formatted})"
                except:
                    cert_text += f" ({cert_date})"
                    
            elements.append(Paragraph(cert_text, styles["Bullet"]))
    
    # Build document
    doc.build(elements)
    
    return output_path