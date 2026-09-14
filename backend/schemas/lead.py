from typing import Optional
from pydantic import BaseModel

class LeadCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
