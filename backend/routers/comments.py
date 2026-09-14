from fastapi import APIRouter, HTTPException, Depends
from database import get_conn
from auth import verify_admin_token
from schemas.content import CommentCreate

router = APIRouter(tags=["Comments & Reviews"])

@router.get("/api/comments")
async def get_comments():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT id, name, country, rating, comment_text, created_at
            FROM comments WHERE is_approved = TRUE ORDER BY created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/comments")
async def add_comment(c: CommentCreate):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO comments (name, country, rating, comment_text) VALUES (%s,%s,%s,%s)",
            (c.name, c.country, min(max(c.rating, 1), 5), c.comment_text)
        )
        conn.commit(); cur.close(); conn.close()
        return {"message": "Comment submitted. It will appear after approval."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/comments/pending")
async def get_pending(_=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT id, name, country, rating, comment_text, created_at
            FROM comments WHERE is_approved = FALSE ORDER BY created_at DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/comments/{cid}/approve")
async def approve_comment(cid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE comments SET is_approved = TRUE WHERE id = %s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/comments/{cid}")
async def delete_comment(cid: int, _=Depends(verify_admin_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM comments WHERE id = %s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
