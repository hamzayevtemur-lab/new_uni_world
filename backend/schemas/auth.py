from typing import Optional
from pydantic import BaseModel

class AdminLogin(BaseModel):
    username: str
    password: str

class StudentRegister(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    target_country: Optional[str] = None
    target_degree: Optional[str] = None
    target_major: Optional[str] = None

class StudentLogin(BaseModel):
    email: str
    password: str
