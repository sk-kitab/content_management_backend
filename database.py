# backend/database.py — re-export from source.database for test imports
from source.database import engine, get_session, SessionLocal, Base  # noqa: F401
