import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # backend/
ROOT_DIR = os.path.dirname(BASE_DIR)                           # uni-world/
FRONTEND = os.path.join(ROOT_DIR, "frontend")

JWT_SECRET = os.getenv("JWT_SECRET", "uni-world-secure-token-secret-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Otaboy")
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$mIbmynOzDKeXHWJa2DShWewN/PGo5eeKN/caw4opVm3cyUP0LK6ay",
)

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "uniworld")

DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 4000))
