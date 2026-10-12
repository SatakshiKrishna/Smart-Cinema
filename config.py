"""Database configuration loaded from a local .env (never commit credentials)."""
import os
from dotenv import load_dotenv
load_dotenv()
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "prachi"),
    "database": os.environ.get("DB_NAME", "smart_cinema"),
}
