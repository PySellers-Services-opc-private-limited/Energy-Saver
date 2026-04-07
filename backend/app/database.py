import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load backend/.env explicitly (root .env has no DB config)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_APP_DIR)
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

# Also load root .env for SMTP / other shared config
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
_DEFAULT_DB = f"sqlite:///{os.path.join(_BACKEND_DIR, 'energy_saver_ai.db')}"

# Use DATABASE_URL env var if set, otherwise use the resolved path
DATABASE_URL: str = os.getenv("DATABASE_URL", _DEFAULT_DB)

# SQLite needs check_same_thread=False for FastAPI's async workers
_connect_args: dict = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()
