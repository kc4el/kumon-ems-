"""Isolated local settings for offline workflow verification."""
from kumon_ems.settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MEDIA_ROOT = BASE_DIR / ".workflow-checks" / "media"
