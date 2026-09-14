import bcrypt
from fastapi import APIRouter, HTTPException
from schemas.auth import AdminLogin
from auth import create_admin_token
from config import ADMIN_USERNAME, ADMIN_PASSWORD_HASH, JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/admin", tags=["Admin Auth"])

@router.post("/login")
async def admin_login(credentials: AdminLogin):
    if credentials.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    try:
        ok = bcrypt.checkpw(credentials.password.encode(), ADMIN_PASSWORD_HASH.encode())
    except Exception:
        raise HTTPException(status_code=500, detail="Auth configuration error")
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"token": create_admin_token(), "expires_in": JWT_EXPIRE_HOURS * 3600, "username": ADMIN_USERNAME}
