import os
from datetime import datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()  # reads .env when running locally; no effect on Render

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import bcrypt

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))          # backend/
ROOT_DIR   = os.path.dirname(BASE_DIR)                           # uni-world/
FRONTEND   = os.path.join(ROOT_DIR, "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
templates  = Jinja2Templates(directory=FRONTEND)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ───────────────────────────────────────────────────────────────────

JWT_SECRET        = os.getenv("JWT_SECRET", "please-change-this-secret")
JWT_ALGORITHM     = "HS256"
JWT_EXPIRE_HOURS  = 8

ADMIN_USERNAME    = os.getenv("ADMIN_USERNAME", "admin")
# Generate hash:  python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpwQCMjBqLLEly",  # "changeme123" – CHANGE IN PRODUCTION
)

# Railway / Neon PostgreSQL — just set DATABASE_URL in your environment
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://user:pass@host:5432/dbname

security = HTTPBearer()

# ── DB ───────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# ── Auth ─────────────────────────────────────────────────────────────────────

def create_token() -> str:
    payload = {
        "sub": "admin",
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("sub") != "admin":
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ── Pydantic models ───────────────────────────────────────────────────────────

class AdminLogin(BaseModel):
    username: str
    password: str

class CommentCreate(BaseModel):
    name: str
    country: str
    rating: int
    comment_text: str

class NewsCreate(BaseModel):
    title: str
    body: str
    badge_text: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    link_text: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    is_ticker: bool = False

class NewsUpdate(NewsCreate):
    pass

# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/admin")
async def admin(request: Request):
    return templates.TemplateResponse(request, "admin.html")

# ── Admin login ───────────────────────────────────────────────────────────────

@app.post("/api/admin/login")
async def admin_login(credentials: AdminLogin):
    if credentials.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        ok = bcrypt.checkpw(credentials.password.encode(), ADMIN_PASSWORD_HASH.encode())
    except Exception:
        raise HTTPException(status_code=500, detail="Auth configuration error")
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(), "expires_in": JWT_EXPIRE_HOURS * 3600}

# ── Comments (public) ─────────────────────────────────────────────────────────

@app.get("/api/comments")
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

@app.post("/api/comments")
async def add_comment(c: CommentCreate):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO comments (name, country, rating, comment_text) VALUES (%s,%s,%s,%s)",
            (c.name, c.country, c.rating, c.comment_text)
        )
        conn.commit(); cur.close(); conn.close()
        return {"message": "Comment submitted. It will appear after approval."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Comments (admin) ──────────────────────────────────────────────────────────

@app.get("/api/comments/pending")
async def get_pending(_=Depends(verify_token)):
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

@app.put("/api/comments/{cid}/approve")
async def approve_comment(cid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE comments SET is_approved = TRUE WHERE id = %s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/comments/{cid}")
async def delete_comment(cid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM comments WHERE id = %s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── News (public) ─────────────────────────────────────────────────────────────

@app.get("/api/news")
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

@app.get("/api/news/ticker")
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

# ── News (admin) ──────────────────────────────────────────────────────────────

@app.get("/api/admin/news")
async def admin_all_news(_=Depends(verify_token)):
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

@app.post("/api/admin/news")
async def create_news(n: NewsCreate, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO news (title, body, badge_text, image_url, link_url, link_text,
                              expires_at, is_active, is_ticker)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (n.title, n.body, n.badge_text, n.image_url, n.link_url, n.link_text,
              n.expires_at, n.is_active, n.is_ticker))
        new_id = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close()
        return {"message": "Created", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/admin/news/{nid}")
async def update_news(nid: int, n: NewsUpdate, _=Depends(verify_token)):
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

@app.delete("/api/admin/news/{nid}")
async def delete_news(nid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM news WHERE id = %s", (nid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── DB setup ──────────────────────────────────────────────────────────────────

@app.get("/setup-db")
def setup_db():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100),
                country     VARCHAR(100),
                rating      INT,
                comment_text TEXT,
                is_approved BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id          SERIAL PRIMARY KEY,
                title       VARCHAR(255) NOT NULL,
                body        TEXT NOT NULL,
                badge_text  VARCHAR(80),
                image_url   VARCHAR(500),
                link_url    VARCHAR(500),
                link_text   VARCHAR(100),
                expires_at  TIMESTAMP,
                is_active   BOOLEAN DEFAULT TRUE,
                is_ticker   BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit(); cur.close(); conn.close()
        return {"message": "Tables created successfully"}
    except Exception as e:
        return {"error": str(e)}

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 4000)))