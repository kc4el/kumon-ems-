"""Run Django verification with all Python network connections blocked.

No production credentials or databases are required. This wrapper is intended
for local tests only; external integration calls must be mocked by their tests.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".testdeps")]
os.chdir(ROOT)


def offline_guard(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("External network access is disabled during offline verification.")


sys.addaudithook(offline_guard)
os.environ["DJANGO_SETTINGS_MODULE"] = "tests.offline_settings"
sys.argv = ["manage.py", "test", *sys.argv[1:], "--noinput"]

from django.core.management import execute_from_command_line

execute_from_command_line(sys.argv)
