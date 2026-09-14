from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class CommentCreate(BaseModel):
    name: str
    country: str
    rating: int
    comment_text: str

class NewsCreate(BaseModel):
    title: str
    body: str
    badge_text: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    link_text: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    is_ticker: bool = False

class NewsUpdate(NewsCreate):
    pass

class CountryCreate(BaseModel):
    name: str
    flag_emoji: str
    university_count: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    modal_key: Optional[str] = None
    programs: Optional[str] = None
    cost_of_living: Optional[str] = None
    language: Optional[str] = None
    visa_requirements: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class CountryUpdate(CountryCreate):
    pass

class ServiceCreate(BaseModel):
    title: str
    icon_emoji: Optional[str] = None
    image_url: Optional[str] = None
    description: str
    details: Optional[str] = None
    benefits: Optional[str] = None
    is_featured: bool = False
    modal_key: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class ServiceUpdate(ServiceCreate):
    pass

class UniversityCreate(BaseModel):
    name: str
    country: str
    image_url: Optional[str] = None
    description: Optional[str] = None
    programs: Optional[str] = None
    ranking: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class UniversityUpdate(UniversityCreate):
    pass
