from typing import Optional
from pydantic import BaseModel

class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    high_school_name: Optional[str] = None
    gpa: Optional[str] = None
    ielts_score: Optional[str] = None
    duolingo_score: Optional[str] = None
    target_country: Optional[str] = None
    target_degree: Optional[str] = None
    target_major: Optional[str] = None

class StudentStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class DocumentCreate(BaseModel):
    doc_type: str
    title: str
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[str] = None

class DocumentReview(BaseModel):
    status: str  # verified / rejected / pending
    admin_feedback: Optional[str] = None

class RequestOTP(BaseModel):
    email: str

class VerifyOTPAndRequestAccess(BaseModel):
    email: str
    otp_code: str
    full_name: str
    phone: Optional[str] = None
    target_country: Optional[str] = None
    target_degree: Optional[str] = None
    target_major: Optional[str] = None
    notes: Optional[str] = None

class ApproveStudentRequest(BaseModel):
    custom_password: Optional[str] = None

