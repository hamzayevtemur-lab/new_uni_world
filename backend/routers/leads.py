from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.lead import LeadCreate

router = APIRouter(tags=["Leads"])

@router.post("/api/leads")
async def submit_lead(lead: LeadCreate):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO leads (name, phone, email, country, message) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (lead.name, lead.phone, lead.email, lead.country, lead.message)
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "message": "Lead received successfully", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/leads")
async def get_admin_leads(_=Depends(verify_admin_token)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
