"""Private Supabase Storage helpers for account profile pictures."""

import os
import uuid
from pathlib import Path

from .supabase_client import supabase


BUCKET = os.getenv("SUPABASE_PROFILE_PICTURE_BUCKET", "profile-pictures")


def _bucket():
    """Return the private bucket, creating it when first needed."""
    try:
        supabase.storage.get_bucket(BUCKET)
    except Exception:
        # A service-role client is used only on the server, so no key reaches
        # browser code.  Pictures remain private and are streamed by Django.
        supabase.storage.create_bucket(BUCKET, options={"public": False})
    return supabase.storage.from_(BUCKET)


def upload(user_id, filename, content, content_type):
    extension = Path(filename).suffix.lower() or ".img"
    key = f"{user_id}/{uuid.uuid4().hex}{extension}"
    _bucket().upload(
        key,
        content,
        file_options={"content-type": content_type, "upsert": "false"},
    )
    return key


def download(key):
    return _bucket().download(key)


def remove(key):
    _bucket().remove([key])


def is_legacy_local_key(key):
    """Older uploads were stored by Django under MEDIA_ROOT."""
    return bool(key and key.startswith("profile-pictures/"))
