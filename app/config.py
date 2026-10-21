import os
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    # Flask Security
    SECRET_KEY = os.getenv("SECRET_KEY", "prod_secret_key_change_in_production_994821")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # Timezone & TOTP
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    SHARED_SECRET = os.getenv("SHARED_SECRET", "JBSWY3DPEHPK3PXP")
    TOTP_INTERVAL = int(os.getenv("TOTP_INTERVAL", 30))

    # Multi-Database Configuration (SQLite, PostgreSQL, MySQL)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///attendance.db")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("mysql://") and not DATABASE_URL.startswith("mysql+"):
        DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }
    if "sqlite" not in DATABASE_URL:
        SQLALCHEMY_ENGINE_OPTIONS["pool_recycle"] = 3600

    # Geofencing Defaults
    DEFAULT_GEOFENCE_RADIUS = float(os.getenv("DEFAULT_GEOFENCE_RADIUS", 100.0))
