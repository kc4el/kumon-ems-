# Kumon EMS

Kumon EMS is a Django-based employee-management dashboard. The server-rendered dashboard now consumes the same-origin Django REST API to display live employee, department, attendance, and leave-request data from Supabase.

## Integrated workflows

| Dashboard area | Backend endpoint(s) | Current behavior |
|---|---|---|
| Overview metrics | `GET /api/dashboard-summary/` | Displays total/active employees, approved leave requests, and pending leave requests. |
| Employee directory | `GET /api/employees/`, `GET /api/departments/` | Renders live expandable employee cards and supports search/filtering. |
| Attendance overview | `GET /api/attendance/` | Renders the latest attendance records on the dashboard. |
| Leave register | `GET /api/leaves/` | Renders current leave applications with employee context. |
| Employee onboarding | `POST /api/employees/` | Creates an employee profile from the onboarding form. |
| Leave application | `POST /api/leaves/` | Submits a pending leave request from the modal form. |

### Auth contract

- Browser dashboard (`static/js/dashboard.js`, via `apiFetch`) uses **session auth + CSRF**: sign in with `POST /api/session-login/` (`{"username", "password"}` → `200` + session cookie; wrong creds → `401`), sign out with `POST /api/session-logout/`. Logged-out API calls get `403` and the JS bounces to `/login/?next=<page>`.
- Scripts/operator use uses tokens: `POST /api/auth-token/` (`{"username", "password"}` → `{"token"}`), then `Authorization: Token <token>`.
- Logged-out rule: everything returns `403` except the public `GET /api/dashboard-summary/` aggregate.

### Error envelope

Every API error body is `{"error": "<string>"}` (statuses untouched). **409 = the request is well-formed but conflicts with current resource state** (duplicate email, double clock-in, overlapping shift, duplicate payroll line); malformed input stays `400`.

### Ops

Preview what the retention purge would delete, then run it:

```bash
python manage.py purge_resigned --dry-run
python manage.py purge_resigned --days 30
```

Run weekly as the operator (example cron — do not install from here):

```cron
0 2 * * 0 cd /path/to/kumon-ems- && .venv/bin/python manage.py purge_resigned >> purge.log 2>&1
```

On Windows use the Task Scheduler equivalent (weekly, same command). Payroll lines are posted manually per pay run — never auto-derived from attendance (overtime/leave-pay rules are unspecified product decisions).

List endpoints are paginated (`results` key, 10 per page).

## Local setup

Create and activate a virtual environment, then install the project packages with valid package names:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install Django djangorestframework django-cors-headers supabase python-dotenv
```

Create a local `.env` file using your own credentials. Do **not** commit it.

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=replace-with-a-server-side-secret
```

## Project structure

- `pages/`: standalone HTML previews (`dashboard.html`, `dashboard-preview.html`, and `login.html`)
- `core/templates/core/`: Django-rendered dashboard and login templates
- `static/css/`: stylesheets
- `static/js/`: browser scripts
- `static/images/`: image assets
- `static/assets/`: source asset data such as the logo base64 file

Apply migrations and start the development server:

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` to use the dashboard.

## Validation

Run the API test suite with:

```bash
python manage.py test api.tests --verbosity 2
```

The suite includes mocked Supabase contracts for existing API routes and the dashboard-summary endpoint.

## Security note

The dashboard intentionally uses same-origin API calls; Supabase credentials remain on the Django server. Before deploying, configure authentication and authorization for every API route, enable appropriate Supabase Row Level Security policies, rotate any credentials that may have been exposed, and set production-safe Django settings.
