from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.content import ServiceCreate, ServiceUpdate

router = APIRouter(tags=["Services"])

@router.get("/api/services")
async def get_services():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM services WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/services")
async def admin_get_services(_=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM services ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/services")
async def create_service(s: ServiceCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO services (title, icon_emoji, image_url, description, details, benefits,
                                  is_featured, modal_key, sort_order, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (s.title, s.icon_emoji, s.image_url, s.description, s.details, s.benefits,
              s.is_featured, s.modal_key, s.sort_order, s.is_active))
        new_id = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close()
        return {"message": "Service created", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/admin/services/{sid}")
async def update_service(sid: int, s: ServiceUpdate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            UPDATE services SET title=%s, icon_emoji=%s, image_url=%s, description=%s,
                details=%s, benefits=%s, is_featured=%s, modal_key=%s,
                sort_order=%s, is_active=%s
            WHERE id=%s
        """, (s.title, s.icon_emoji, s.image_url, s.description, s.details, s.benefits,
              s.is_featured, s.modal_key, s.sort_order, s.is_active, sid))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/admin/services/{sid}")
async def delete_service(sid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM services WHERE id=%s", (sid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
