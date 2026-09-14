from typing import Optional
from pydantic import BaseModel

class ApplicationCreate(BaseModel):
    university_name: str
    country: Optional[str] = None
    program_name: Optional[str] = None
    intake_semester: Optional[str] = None
    status: Optional[str] = "Draft"
    portal_url: Optional[str] = None
    application_id: Optional[str] = None
    notes: Optional[str] = None
