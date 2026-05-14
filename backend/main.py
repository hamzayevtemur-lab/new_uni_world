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

# ── Countries ─────────────────────────────────────────────────────────────────

class CountryCreate(BaseModel):
    name: str
    flag_emoji: str
    university_count: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    modal_key: Optional[str] = None
    programs: Optional[str] = None          # comma-separated
    cost_of_living: Optional[str] = None    # e.g. $400-600/month
    language: Optional[str] = None
    visa_requirements: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class CountryUpdate(CountryCreate):
    pass

@app.get("/api/countries")
async def get_countries():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM countries WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/countries")
async def admin_get_countries(_=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM countries ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/countries")
async def create_country(c: CountryCreate, _=Depends(verify_token)):
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

@app.put("/api/admin/countries/{cid}")
async def update_country(cid: int, c: CountryUpdate, _=Depends(verify_token)):
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

@app.delete("/api/admin/countries/{cid}")
async def delete_country(cid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM countries WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Services ──────────────────────────────────────────────────────────────────

class ServiceCreate(BaseModel):
    title: str
    icon_emoji: Optional[str] = None
    image_url: Optional[str] = None
    description: str
    details: Optional[str] = None
    benefits: Optional[str] = None
    is_featured: bool = False
    modal_key: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class ServiceUpdate(ServiceCreate):
    pass

@app.get("/api/services")
async def get_services():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM services WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/services")
async def admin_get_services(_=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM services ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/services")
async def create_service(s: ServiceCreate, _=Depends(verify_token)):
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

@app.put("/api/admin/services/{sid}")
async def update_service(sid: int, s: ServiceUpdate, _=Depends(verify_token)):
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

@app.delete("/api/admin/services/{sid}")
async def delete_service(sid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM services WHERE id=%s", (sid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Universities ──────────────────────────────────────────────────────────────

class UniversityCreate(BaseModel):
    name: str
    country: str
    image_url: Optional[str] = None
    description: Optional[str] = None
    programs: Optional[str] = None    # comma-separated list
    ranking: Optional[str] = None     # e.g. "QS Top 500"
    link_url: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class UniversityUpdate(UniversityCreate):
    pass

@app.get("/api/universities")
async def get_universities():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM universities WHERE is_active=TRUE ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/universities")
async def admin_get_universities(_=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM universities ORDER BY sort_order, id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/universities")
async def create_university(u: UniversityCreate, _=Depends(verify_token)):
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

@app.put("/api/admin/universities/{uid}")
async def update_university(uid: int, u: UniversityUpdate, _=Depends(verify_token)):
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

@app.delete("/api/admin/universities/{uid}")
async def delete_university(uid: int, _=Depends(verify_token)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM universities WHERE id=%s", (uid,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id                SERIAL PRIMARY KEY,
                name              VARCHAR(100) NOT NULL,
                flag_emoji        VARCHAR(10),
                university_count  VARCHAR(50),
                description       TEXT,
                image_url         VARCHAR(500),
                modal_key         VARCHAR(50),
                programs          TEXT,          -- comma-separated
                cost_of_living    VARCHAR(100),  -- e.g. $400-600/month
                language          TEXT,
                visa_requirements TEXT,
                sort_order        INT DEFAULT 0,
                is_active         BOOLEAN DEFAULT TRUE,
                created_at        TIMESTAMP DEFAULT NOW()
            )
        """)
        # Add new columns to existing countries table if they don't exist yet
        for col, typedef in [
            ("programs", "TEXT"),
            ("cost_of_living", "VARCHAR(100)"),
            ("language", "TEXT"),
            ("visa_requirements", "TEXT"),
        ]:
            cur.execute(f"""
                DO $$ BEGIN
                    ALTER TABLE countries ADD COLUMN {col} {typedef};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id            SERIAL PRIMARY KEY,
                title         VARCHAR(200) NOT NULL,
                icon_emoji    VARCHAR(10),
                image_url     VARCHAR(500),
                description   TEXT,
                details       TEXT,   -- newline-separated bullet points
                benefits      TEXT,
                is_featured   BOOLEAN DEFAULT FALSE,
                modal_key     VARCHAR(50),
                sort_order    INT DEFAULT 0,
                is_active     BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """)
        # Add new columns to existing services table if they don't exist yet
        for col, typedef in [
            ("details", "TEXT"),
            ("benefits", "TEXT"),
            ("image_url", "VARCHAR(500)"),
        ]:
            cur.execute(f"""
                DO $$ BEGIN
                    ALTER TABLE services ADD COLUMN {col} {typedef};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS universities (
                id           SERIAL PRIMARY KEY,
                name         VARCHAR(200) NOT NULL,
                country      VARCHAR(100),
                image_url    VARCHAR(500),
                description  TEXT,
                programs     TEXT,
                ranking      VARCHAR(100),
                link_url     VARCHAR(500),
                sort_order   INT DEFAULT 0,
                is_active    BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit(); cur.close(); conn.close()
        return {"message": "All tables created successfully"}
    except Exception as e:
        return {"error": str(e)}

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 4000)))