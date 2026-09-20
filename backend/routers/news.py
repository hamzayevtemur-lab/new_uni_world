from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.content import NewsCreate, NewsUpdate

router = APIRouter(tags=["News & Announcements"])

@router.get("/api/news")
async def get_news():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT id, title, body, badge_text, image_url, link_url, link_text,
                   expires_at, is_active, is_ticker, created_at
            FROM news
            WHERE is_active = TRUE AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/news/ticker")
async def get_ticker():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT id, title, badge_text, link_url FROM news
            WHERE is_active = TRUE AND is_ticker = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/news")
async def admin_all_news(_=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT id, title, body, badge_text, image_url, link_url, link_text,
                   expires_at, is_active, is_ticker, created_at
            FROM news ORDER BY created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/news")
async def create_news(n: NewsCreate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO news (title, body, badge_text, image_url, link_url, link_text,
                              expires_at, is_active, is_ticker)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (n.title, n.body, n.badge_text, n.image_url, n.link_url, n.link_text,
              n.expires_at, n.is_active, n.is_ticker))
        new_id = cur.lastrowid
        conn.commit(); cur.close(); conn.close()
        return {"message": "Created", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/admin/news/{nid}")
async def update_news(nid: int, n: NewsUpdate, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            UPDATE news SET title=%s, body=%s, badge_text=%s, image_url=%s,
                link_url=%s, link_text=%s, expires_at=%s, is_active=%s, is_ticker=%s
            WHERE id=%s
        """, (n.title, n.body, n.badge_text, n.image_url, n.link_url, n.link_text,
              n.expires_at, n.is_active, n.is_ticker, nid))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/admin/news/{nid}")
async def delete_news(nid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM news WHERE id = %s", (nid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
