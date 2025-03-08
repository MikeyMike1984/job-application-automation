# app/db/repositories/__init__.py
from app.db.repositories.jobs import JobsRepository
from app.db.repositories.profiles import ProfilesRepository
from app.db.repositories.resumes import ResumesRepository

__all__ = [
    'JobsRepository',
    'ProfilesRepository',
    'ResumesRepository'
]