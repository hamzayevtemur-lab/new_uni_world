from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.content import CountryCreate, CountryUpdate

router = APIRouter(tags=["Countries"])

@router.get("/api/countries")
async def get_countries():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM countries WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/countries")
async def admin_get_countries(_=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM countries ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/countries")
async def create_country(c: CountryCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO countries (name, flag_emoji, university_count, description,
                                   image_url, modal_key, programs, cost_of_living,
                                   language, visa_requirements, sort_order, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (c.name, c.flag_emoji, c.university_count, c.description,
              c.image_url, c.modal_key, c.programs, c.cost_of_living,
              c.language, c.visa_requirements, c.sort_order, c.is_active))
        new_id = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close()
        return {"message": "Country created", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/admin/countries/{cid}")
async def update_country(cid: int, c: CountryUpdate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            UPDATE countries SET name=%s, flag_emoji=%s, university_count=%s,
                description=%s, image_url=%s, modal_key=%s, programs=%s,
                cost_of_living=%s, language=%s, visa_requirements=%s,
                sort_order=%s, is_active=%s
            WHERE id=%s
        """, (c.name, c.flag_emoji, c.university_count, c.description,
              c.image_url, c.modal_key, c.programs, c.cost_of_living,
              c.language, c.visa_requirements, c.sort_order, c.is_active, cid))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/admin/countries/{cid}")
async def delete_country(cid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM countries WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
