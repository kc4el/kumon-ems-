# Purge scheduling (SOP 5 — 30-day retention)

`purge_resigned` is an **unscheduled operational policy** (per Chapter 3, §3.4.5): the
30-day window is enforced by whoever runs the command, not by an in-code scheduler.
The API endpoint `POST /api/purge-run/` and the admin panel are the manual paths.

## Preview (safe, never deletes)

```bash
DB_HOST= ./.venv/Scripts/python manage.py purge_resigned --dry-run --days 30
```

Expected output — one line per eligible row, exit code 0:

```
would purge <employee-uuid> <email>
```

## Real run (deletes local row + Supabase auth user)

```bash
DB_HOST= ./.venv/Scripts/python manage.py purge_resigned --days 30
```

Expected output: `purged <email>` per row. Rows whose Supabase delete fails print
`skipped <email>: upstream delete failed` and are retried on the next run.
Every purge writes an `EmployeeAuditLog` row containing the employee **id and email**
before the row is deleted, so attribution survives the erase.

## Recommended cadence — Windows Task Scheduler (weekly)

1. Task Scheduler → Create Task → name `Kumon EMS purge resigned`.
2. Trigger: Weekly, Monday 02:00 (off-hours, office machine on).
3. Action → Start a program:
   - Program: `C:\Users\mikae\OneDrive\Desktop\Codes\transit-planner\kumon-ems-\.venv\Scripts\python.exe`
   - Arguments: `manage.py purge_resigned --days 30`
   - Start in: `C:\Users\mikae\OneDrive\Desktop\Codes\transit-planner\kumon-ems-`
4. Set `DB_HOST` for the task env if the shared Postgres is the target, otherwise
   leave it blank for the local SQLite file.

> Never put credentials in this file or in the task arguments — `.env` owns them.
