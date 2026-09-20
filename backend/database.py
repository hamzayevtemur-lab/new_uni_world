import os
import urllib.parse
from dotenv import load_dotenv
import pymysql
import pymysql.cursors

load_dotenv()


def get_database_url() -> str:
    """
    Builds the database URL from environment variables.

    Production (Railway / Hetzner / Docker) → uses MYSQLHOST or DATABASE_URL
    Local development                       → uses MYSQL_HOST / DB_HOST from .env
    """
    if os.environ.get("DATABASE_URL"):
        return os.environ.get("DATABASE_URL")

    if os.environ.get("MYSQLHOST"):
        host = os.environ.get("MYSQLHOST")
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "root")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "uniworld")
        return f"mysql://{user}:{password}@{host}:{port}/{database}"

    # Local development
    host = os.environ.get("MYSQL_HOST") or os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT") or os.environ.get("DB_PORT", "3306")
    user = os.environ.get("MYSQL_USER") or os.environ.get("DB_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD") or os.environ.get("DB_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME", "uniworld")
    return f"mysql://{user}:{password}@{host}:{port}/{database}"


DATABASE_URL = get_database_url()


def get_conn():
    """Establishes connection to MySQL database using PyMySQL and returns DictCursor."""
    url_clean = DATABASE_URL.replace("mysql+pymysql://", "mysql://")
    parsed = urllib.parse.urlparse(url_clean)
    return pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=int(parsed.port or 3306),
        user=parsed.username or "root",
        password=parsed.password or "",
        database=parsed.path.lstrip("/") or "uniworld",
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
