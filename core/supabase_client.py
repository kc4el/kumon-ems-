import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def rollback_supabase_user(created_user_id, log=None):
    """Safely delete an orphaned Supabase user if downstream creation fails."""
    if not created_user_id:
        return
    try:
        supabase.auth.admin.delete_user(str(created_user_id))
    except Exception:
        if log:
            log.exception(f"Unable to roll back Supabase Auth user {created_user_id}")

