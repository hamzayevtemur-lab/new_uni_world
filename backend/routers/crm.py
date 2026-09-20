import json
import random
import bcrypt
import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.student import StudentStatusUpdate, DocumentReview, ApproveStudentRequest
from schemas.application import ApplicationCreate
from services.email_service import send_student_credentials_email

router = APIRouter(prefix="/api/admin", tags=["Agency Student CRM"])

@router.get("/student-requests")
async def admin_get_student_requests(_=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, full_name, phone, target_country, target_degree, target_major,
                   status, email_verified, notes, created_at, updated_at
            FROM students
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/student-requests/{sid}/approve")
async def admin_approve_student_request(sid: int, body: Optional[ApproveStudentRequest] = None, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
        student = cur.fetchone()
        if not student:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Student request not found")

        raw_password = (body.custom_password.strip() if body and body.custom_password else None)
        if not raw_password:
            raw_password = f"UniWorld#{random.randint(1000, 9999)}"

        pwd_hash = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cur.execute("""
            UPDATE students SET
                status = 'active',
                password_hash = %s,
                approved_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (pwd_hash, sid))

        cur.execute("SELECT id, email, full_name, status, approved_at FROM students WHERE id = %s", (sid,))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        sent = send_student_credentials_email(student["email"], student["full_name"], raw_password)

        return {
            "message": f"Student {student['full_name']} approved! Login credentials emailed.",
            "student_id": sid,
            "email": student["email"],
            "assigned_password": raw_password,
            "email_sent": sent
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/student-requests/{sid}/reject")
async def admin_reject_student_request(sid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE students SET status = 'rejected', updated_at = NOW() WHERE id = %s", (sid,))
        cur.execute("SELECT id, status FROM students WHERE id = %s", (sid,))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Access request declined", "student": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/students")
async def admin_get_all_students(_=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.email, s.full_name, s.phone, s.nationality, s.passport_number,
                   s.target_country, s.target_degree, s.target_major, s.status, s.created_at, s.updated_at,
                   COUNT(d.id) AS document_count,
                   COUNT(CASE WHEN d.status = 'verified' THEN 1 END) AS verified_doc_count,
                   COUNT(a.id) AS application_count
            FROM students s
            LEFT JOIN student_documents d ON d.student_id = s.id
            LEFT JOIN student_applications a ON a.student_id = s.id
            GROUP BY s.id, s.email, s.full_name, s.phone, s.nationality, s.passport_number,
                     s.target_country, s.target_degree, s.target_major, s.status, s.created_at, s.updated_at
            ORDER BY s.updated_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/students/{sid}")
async def admin_get_student_detail(sid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        del student["password_hash"]
        
        cur.execute("SELECT * FROM student_documents WHERE student_id = %s ORDER BY uploaded_at DESC", (sid,))
        docs = cur.fetchall()
        
        cur.execute("SELECT * FROM student_applications WHERE student_id = %s ORDER BY created_at DESC", (sid,))
        apps = cur.fetchall()
        
        cur.close()
        conn.close()
        return {"student": student, "documents": docs, "applications": apps}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/students/{sid}/status")
async def admin_update_student_status(sid: int, status_data: StudentStatusUpdate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE students SET status = %s, notes = COALESCE(%s, notes), updated_at = NOW()
            WHERE id = %s
        """, (status_data.status, status_data.notes, sid))
        cur.execute("SELECT id, status, notes FROM students WHERE id = %s", (sid,))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"student": updated, "message": "Status updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/documents/{doc_id}/review")
async def admin_review_document(doc_id: int, review: DocumentReview, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE student_documents
            SET status = %s, admin_feedback = %s
            WHERE id = %s
        """, (review.status, review.admin_feedback, doc_id))
        cur.execute("SELECT id, student_id, status, admin_feedback FROM student_documents WHERE id = %s", (doc_id,))
        doc = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"document": doc, "message": "Document review saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/students/{sid}/applications")
async def admin_create_application(sid: int, app_data: ApplicationCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO student_applications (student_id, university_name, country, program_name, intake_semester, status, portal_url, application_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (sid, app_data.university_name, app_data.country, app_data.program_name, app_data.intake_semester, app_data.status, app_data.portal_url, app_data.application_id, app_data.notes))
        new_id = cur.lastrowid
        
        if app_data.status in ["Submitted to University", "Applied"]:
            cur.execute("UPDATE students SET status = 'Applied', updated_at = NOW() WHERE id = %s", (sid,))
            
        conn.commit()
        cur.close()
        conn.close()
        return {"id": new_id, "message": "University application created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/applications/{app_id}")
async def admin_update_application(app_id: int, app_data: ApplicationCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE student_applications SET
                university_name = %s,
                country = %s,
                program_name = %s,
                intake_semester = %s,
                status = %s,
                portal_url = %s,
                application_id = %s,
                notes = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (app_data.university_name, app_data.country, app_data.program_name, app_data.intake_semester, app_data.status, app_data.portal_url, app_data.application_id, app_data.notes, app_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Application updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/applications/{app_id}")
async def admin_delete_application(app_id: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM student_applications WHERE id = %s", (app_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Application removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/students/{sid}/autofill-payload")
async def admin_get_autofill_payload(sid: int, target_uni: Optional[str] = "Wuxi University", _=Depends(verify_admin_token)):
    """Generates structured standard fields and ready-to-execute JavaScript bookmarklet snippet for university application portals."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
        s = cur.fetchone()
        if not s:
            raise HTTPException(status_code=404, detail="Student not found")
            
        cur.execute("SELECT * FROM student_documents WHERE student_id = %s", (sid,))
        docs = cur.fetchall()
        cur.close()
        conn.close()
        
        name_parts = (s.get("full_name") or "").strip().split(" ")
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        doc_map = {}
        for d in docs:
            doc_map[d["doc_type"]] = d["file_url"]

        data_package = {
            "student_id": s["id"],
            "target_university": target_uni,
            "fields": {
                "fullName": s.get("full_name", ""),
                "firstName": first_name,
                "lastName": last_name,
                "email": s.get("email", ""),
                "phone": s.get("phone", ""),
                "dateOfBirth": s.get("date_of_birth", ""),
                "gender": s.get("gender", ""),
                "nationality": s.get("nationality", "Uzbekistan"),
                "passportNumber": s.get("passport_number", ""),
                "passportExpiry": s.get("passport_expiry", ""),
                "address": s.get("address", ""),
                "emergencyContact": s.get("emergency_contact", ""),
                "highSchool": s.get("high_school_name", ""),
                "gpa": s.get("gpa", ""),
                "ielts": s.get("ielts_score", ""),
                "duolingo": s.get("duolingo_score", ""),
                "degreeLevel": s.get("target_degree", "Bachelor"),
                "major": s.get("target_major", "")
            },
            "documents": doc_map
        }

        autofill_js = f"""(function(){{
    const d = {json.dumps(data_package['fields'])};
    console.log('Uni World Autofill Activated for', d.fullName);
    const map = {{
        'input[name*="name" i], input[id*="name" i], input[placeholder*="name" i]': d.fullName,
        'input[name*="first" i], input[id*="first" i]': d.firstName,
        'input[name*="last" i], input[id*="last" i], input[name*="sur" i]': d.lastName,
        'input[type="email"], input[name*="mail" i], input[id*="mail" i]': d.email,
        'input[type="tel"], input[name*="phone" i], input[id*="phone" i], input[name*="mobile" i]': d.phone,
        'input[name*="pass" i], input[id*="pass" i], input[placeholder*="passport" i]': d.passportNumber,
        'input[name*="birth" i], input[id*="birth" i], input[name*="dob" i]': d.dateOfBirth,
        'input[name*="nation" i], input[id*="nation" i]': d.nationality,
        'input[name*="address" i], textarea[name*="address" i]': d.address,
        'input[name*="gpa" i], input[id*="gpa" i]': d.gpa,
        'input[name*="school" i], input[id*="school" i]': d.highSchool,
        'input[name*="ielts" i], input[id*="ielts" i]': d.ielts,
        'input[name*="major" i], input[id*="major" i]': d.major
    }};
    let filled = 0;
    for(let selector in map){{
        const val = map[selector];
        if(!val) continue;
        document.querySelectorAll(selector).forEach(el => {{
            if(el && el.value !== undefined && !el.value){{
                el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.style.backgroundColor = '#d1fae5';
                filled++;
            }}
        }});
    }}
    alert('Uni World: Successfully auto-filled ' + filled + ' fields for ' + d.fullName + '!');
}})();"""

        return {
            "package": data_package,
            "bookmarklet_code": autofill_js
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
