from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.content import UniversityCreate, UniversityUpdate

router = APIRouter(tags=["Universities"])

@router.get("/api/universities")
async def get_universities():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM universities WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/universities")
async def admin_get_universities(_=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM universities ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/universities")
async def create_university(u: UniversityCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO universities (name, country, image_url, description,
                                      programs, ranking, link_url, sort_order, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (u.name, u.country, u.image_url, u.description,
              u.programs, u.ranking, u.link_url, u.sort_order, u.is_active))
        new_id = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close()
        return {"message": "University created", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/admin/universities/{uid}")
async def update_university(uid: int, u: UniversityUpdate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            UPDATE universities SET name=%s, country=%s, image_url=%s, description=%s,
                programs=%s, ranking=%s, link_url=%s, sort_order=%s, is_active=%s
            WHERE id=%s
        """, (u.name, u.country, u.image_url, u.description,
              u.programs, u.ranking, u.link_url, u.sort_order, u.is_active, uid))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/admin/universities/{uid}")
async def delete_university(uid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM universities WHERE id=%s", (uid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
