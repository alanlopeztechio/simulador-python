"""
Company model for managing transport companies.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Company:
    """Represents a transport company."""
    
    name: str
    description: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self):
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Company instance from dictionary."""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            description=data.get('description', ''),
            contact_email=data.get('contact_email', ''),
            contact_phone=data.get('contact_phone', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def __str__(self):
        return self.name
