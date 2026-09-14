from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import FRONTEND, PORT
from database import init_db
from routers import (
    auth_router,
    student_router,
    crm_router,
    leads_router,
    comments_router,
    news_router,
    countries_router,
    services_router,
    universities_router,
)

# ── App Initialization ────────────────────────────────────────────────────────

app = FastAPI(title="Uni World API & CRM", version="2.0")

# Static assets & Jinja2 Templates
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
templates = Jinja2Templates(directory=FRONTEND)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PostgreSQL schema tables on startup
@app.on_event("startup")
def on_startup():
    init_db()

# ── Register Routers ─────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(student_router)
app.include_router(crm_router)
app.include_router(leads_router)
app.include_router(comments_router)
app.include_router(news_router)
app.include_router(countries_router)
app.include_router(services_router)
app.include_router(universities_router)

# ── Frontend Page Views ──────────────────────────────────────────────────────

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/admin")
async def admin(request: Request):
    return templates.TemplateResponse(request, "admin.html")

@app.get("/student")
@app.get("/student-portal")
async def student_portal(request: Request):
    return templates.TemplateResponse(request, "student.html")

# ── Run Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)