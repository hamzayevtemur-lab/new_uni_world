import random
import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import create_student_token, verify_student_token
from schemas.auth import StudentLogin
from schemas.student import (
    StudentProfileUpdate,
    DocumentCreate,
    RequestOTP,
    VerifyOTPAndRequestAccess,
)
from services.email_service import send_otp_email
from config import JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/student", tags=["Student Portal"])

@router.post("/request-otp")
async def student_request_otp(data: RequestOTP):
    email_clean = data.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="A valid email address is required")

    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT id, status, email_verified FROM students WHERE email = %s", (email_clean,))
        student = cur.fetchone()

        if student and student["status"] in ["active", "Approved", "Docs Submitted"]:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Account already active! Please proceed to Log In.")

        if student:
            cur.execute("""
                UPDATE students
                SET otp_code = %s, otp_expires_at = %s, updated_at = NOW()
                WHERE id = %s
            """, (otp_code, expires_at, student["id"]))
        else:
            cur.execute("""
                INSERT INTO students (email, full_name, status, email_verified, otp_code, otp_expires_at)
                VALUES (%s, 'Pending Applicant', 'pending', FALSE, %s, %s)
            """, (email_clean, otp_code, expires_at))

        conn.commit()
        cur.close()
        conn.close()

        # Send OTP email
        sent = send_otp_email(email_clean, otp_code)
        return {
            "message": "Verification code sent to your email! Please check your inbox.",
            "email": email_clean,
            "dev_otp": otp_code
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-otp-and-request-access")
async def student_verify_otp(data: VerifyOTPAndRequestAccess):
    email_clean = data.email.strip().lower()
    otp_clean = data.otp_code.strip()

    if not email_clean or not otp_clean:
        raise HTTPException(status_code=400, detail="Email and verification code are required")

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT * FROM students WHERE email = %s", (email_clean,))
        student = cur.fetchone()

        if not student:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="No verification request found for this email.")

        if not student["otp_code"] or student["otp_code"].strip() != otp_clean:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid 6-digit verification code. Please try again.")

        if student["otp_expires_at"] and student["otp_expires_at"] < datetime.datetime.utcnow():
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")

        # Update student to email_verified = True and status = 'pending'
        cur.execute("""
            UPDATE students SET
                full_name = %s,
                phone = %s,
                target_country = %s,
                target_degree = %s,
                target_major = %s,
                notes = %s,
                email_verified = TRUE,
                status = 'pending',
                otp_code = NULL,
                updated_at = NOW()
            WHERE id = %s
        """, (
            data.full_name, data.phone, data.target_country,
            data.target_degree, data.target_major, data.notes,
            student["id"]
        ))

        cur.execute("SELECT id, email, full_name, status, email_verified FROM students WHERE id = %s", (student["id"],))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return {
            "message": "Email verified successfully! Your portal access request has been sent to our counselors.",
            "student": updated
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def student_login(creds: StudentLogin):
    email_clean = creds.email.strip().lower()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE email = %s", (email_clean,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if not student:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if student["status"] == "pending":
            raise HTTPException(
                status_code=403,
                detail="Your access request is currently pending admin approval. Credentials will be sent to your email once approved."
            )

        if student["status"] == "rejected":
            raise HTTPException(status_code=403, detail="Your access request was declined. Please contact support.")

        if not student["password_hash"]:
            raise HTTPException(status_code=401, detail="No active password set for this account.")

        ok = bcrypt.checkpw(creds.password.encode('utf-8'), student["password_hash"].encode('utf-8'))
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_student_token(student["id"], student["email"])
        del student["password_hash"]
        return {
            "token": token,
            "student": student,
            "expires_in": JWT_EXPIRE_HOURS * 3600
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def student_get_me(current=Depends(verify_student_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (current["student_id"],))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        del student["password_hash"]
        
        cur.execute("SELECT * FROM student_documents WHERE student_id = %s ORDER BY uploaded_at DESC", (current["student_id"],))
        docs = cur.fetchall()
        
        cur.execute("SELECT * FROM student_applications WHERE student_id = %s ORDER BY created_at DESC", (current["student_id"],))
        apps = cur.fetchall()
        
        cur.close()
        conn.close()
        return {"student": student, "documents": docs, "applications": apps}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/profile")
async def student_update_profile(p: StudentProfileUpdate, current=Depends(verify_student_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE students SET
                full_name = COALESCE(%s, full_name),
                phone = COALESCE(%s, phone),
                date_of_birth = COALESCE(%s, date_of_birth),
                gender = COALESCE(%s, gender),
                nationality = COALESCE(%s, nationality),
                passport_number = COALESCE(%s, passport_number),
                passport_expiry = COALESCE(%s, passport_expiry),
                address = COALESCE(%s, address),
                emergency_contact = COALESCE(%s, emergency_contact),
                high_school_name = COALESCE(%s, high_school_name),
                gpa = COALESCE(%s, gpa),
                ielts_score = COALESCE(%s, ielts_score),
                duolingo_score = COALESCE(%s, duolingo_score),
                target_country = COALESCE(%s, target_country),
                target_degree = COALESCE(%s, target_degree),
                target_university = COALESCE(%s, target_university),
                target_major = COALESCE(%s, target_major),
                secondary_major = COALESCE(%s, secondary_major),
                instruction_language = COALESCE(%s, instruction_language),
                updated_at = NOW()
            WHERE id = %s
        """, (
            p.full_name, p.phone, p.date_of_birth, p.gender, p.nationality,
            p.passport_number, p.passport_expiry, p.address, p.emergency_contact,
            p.high_school_name, p.gpa, p.ielts_score, p.duolingo_score,
            p.target_country, p.target_degree, p.target_university,
            p.target_major, p.secondary_major, p.instruction_language,
            current["student_id"]
        ))
        cur.execute("SELECT * FROM students WHERE id = %s", (current["student_id"],))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        del updated["password_hash"]
        return {"student": updated, "message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents")
async def student_upload_document(doc: DocumentCreate, current=Depends(verify_student_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO student_documents (student_id, doc_type, title, file_url, file_name, file_size, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (current["student_id"], doc.doc_type, doc.title, doc.file_url, doc.file_name, doc.file_size))
        
        doc_id = cur.lastrowid
        cur.execute("SELECT id, doc_type, title, file_url, status, uploaded_at FROM student_documents WHERE id = %s", (doc_id,))
        new_doc = cur.fetchone()
        
        cur.execute("SELECT status FROM students WHERE id = %s", (current["student_id"],))
        s_row = cur.fetchone()
        if s_row and s_row["status"] == "Registered":
            cur.execute("UPDATE students SET status = 'Docs Submitted', updated_at = NOW() WHERE id = %s", (current["student_id"],))
            
        conn.commit()
        cur.close()
        conn.close()
        return {"document": new_doc, "message": "Document uploaded successfully and queued for verification"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{doc_id}")
async def student_delete_document(doc_id: int, current=Depends(verify_student_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM student_documents WHERE id = %s AND student_id = %s", (doc_id, current["student_id"]))
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Document removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
