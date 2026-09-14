import bcrypt
from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import create_student_token, verify_student_token
from schemas.auth import StudentRegister, StudentLogin
from schemas.student import StudentProfileUpdate, DocumentCreate
from config import JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/student", tags=["Student Portal"])

@router.post("/register")
async def student_register(data: StudentRegister):
    email_clean = data.email.strip().lower()
    if not email_clean or not data.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    
    pwd_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM students WHERE email = %s", (email_clean,))
        if cur.fetchone():
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="An account with this email already exists.")
        
        cur.execute("""
            INSERT INTO students (email, password_hash, full_name, phone, target_country, target_degree, target_major)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, email, full_name, status
        """, (email_clean, pwd_hash, data.full_name, data.phone, data.target_country, data.target_degree, data.target_major))
        
        student = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        token = create_student_token(student["id"], student["email"])
        return {
            "token": token,
            "student": student,
            "message": "Account created successfully"
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
                target_major = COALESCE(%s, target_major),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """, (
            p.full_name, p.phone, p.date_of_birth, p.gender, p.nationality,
            p.passport_number, p.passport_expiry, p.address, p.emergency_contact,
            p.high_school_name, p.gpa, p.ielts_score, p.duolingo_score,
            p.target_country, p.target_degree, p.target_major,
            current["student_id"]
        ))
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
            RETURNING id, doc_type, title, file_url, status, uploaded_at
        """, (current["student_id"], doc.doc_type, doc.title, doc.file_url, doc.file_name, doc.file_size))
        
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
