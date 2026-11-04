# Kumon EMS

Kumon EMS is a Django-based employee-management dashboard. The server-rendered dashboard now consumes the same-origin Django REST API to display live employee, department, attendance, and leave-request data from Supabase.

## Employee portal data mapping

The employee portal uses Django session authentication and the shared Django tables. Non-staff create requests do not trust an employee id supplied by the browser; the backend resolves `request.user.employee_profile` and overwrites the foreign key before saving.

| Portal action | API | Shared table | Ownership rule |
| --- | --- | --- | --- |
| Clock in/out | `POST /api/attendance/me/` with `action` | `core_attendance` | Session user is resolved to `Employee`; date and timestamps are server-side. |
| Attendance history | `GET /api/attendance/me/` | `core_attendance` | Returns only the authenticated employee's rows. |
| Leave request | `POST /api/leaves/` | `core_leaverequest` | `ForceOwnerCreateMixin` replaces a non-staff employee id with the session owner. Lists use `employee__user` filtering. |
| Complaint filing | `POST /api/complaints/` | `core_complaint` | Non-staff submissions are assigned to the session owner; list/detail access uses owner permissions. |
| Salary advance | `POST /api/advances/` | `core_salaryadvance` | Non-staff submissions are assigned to the session owner; list/detail access uses owner permissions. |

This is the Django equivalent of Supabase RLS: the browser only calls same-origin endpoints with CSRF protection, and server-side queryset scoping prevents employees from reading or writing another employee's records. Supabase access remains server-side through `core.supabase_client`; no service key is exposed to portal JavaScript.

## Integrated workflows

| Dashboard area | Backend endpoint(s) | Current behavior |
|---|---|---|
| Overview metrics | `GET /api/dashboard-summary/` | Displays total/active employees, approved leave requests, and pending leave requests. |
| Employee directory | `GET /api/employees/`, `GET /api/departments/` | Renders live expandable employee cards and supports search/filtering. |
| Attendance overview | `GET /api/attendance/` | Renders the latest attendance records on the dashboard. |
| Leave register | `GET /api/leaves/` | Renders current leave applications with employee context. |
| New hire onboarding | `POST /api/hr/employees/onboard/` | HR-only creation of a new employee, unique `EMP-YYYY-XXXX` ID, and one-time Argon2id-hashed temporary password. Credentials are returned once with `Cache-Control: no-store`; existing employees cannot be selected for regeneration. |
| First-time account activation | `POST /api/auth/employee-login` | The single-use HR credential activates the account, becomes its initial password, and opens the employee portal. |
| Employee documents | `GET/POST /api/onboarding-docs/`, `GET/PATCH/DELETE /api/onboarding-docs/<uuid>/`, `GET /api/onboarding-docs/<uuid>/download/` | HR can view, add, replace, reclassify, and delete employee files from the roster profile. Employees can view and download only their own files; download links are authenticated rather than direct media URLs. |
| Leave application | `POST /api/leaves/` | Submits a pending leave request from the modal form. |

### Auth contract

- Browser dashboard (`static/js/dashboard.js`, via `apiFetch`) uses **session auth + CSRF**: sign in with `POST /api/session-login/`; accounts with 2FA complete `POST /api/session-verify-2fa/` before receiving a session. Sign out with `POST /api/session-logout/`.
- The login page has three HR-managed paths: Employee ID/linked-email plus password for returning staff; a collapsible first-time form for HR-issued Employee ID and temporary password; and a separate HR login. Google sign-in is disabled. The legacy `POST /api/employees/` endpoint remains HR-only; anonymous self-registration is disabled.
- Scripts/operator use uses tokens: `POST /api/auth-token/` (`{"username", "password"}`; add `code` for accounts with 2FA → `{"token"}`), then `Authorization: Token <token>`.
- Authenticator setup is available from **My account** (`/api/settings/2fa/setup/`, `/confirm/`, `/disable/`). Recovery codes are shown once, stored as hashes, and consumed individually. Configure a stable `MFA_ENCRYPTION_KEY` for deployments; otherwise the key derives from Django's `SECRET_KEY`, so rotating that key makes saved authenticators unreadable.
- HR can open **Employee Management → Onboard New Employee** to create a new-hire record and issue credentials as one operation. The temporary password appears only in the one-time handover modal, expires in 24 hours, and becomes the employee's initial password at first sign-in. Existing employee records cannot be selected for credential regeneration. Employees can change their password later in account settings. Linking a Google account is optional in employee account settings; OAuth uses authorization-code exchange, verified Google ID tokens, session-bound state, and nonce validation.
- To enable optional Google account linking, configure a Google OAuth Web application and register `/api/auth/google/callback/`. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in the server environment. Optionally set `GOOGLE_OAUTH_ALLOWED_DOMAIN` to require a verified corporate email domain; production callback URLs must use HTTPS.
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
# Supabase Postgres URL from Project Settings > Connect.
# Use direct connection on IPv6 (or IPv4 add-on); use session pooler on IPv4-only hosts.
SUPABASE_DB_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres
# Optional dedicated Fernet key for encrypting authenticator secrets.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Keep this value stable across deployments and Django SECRET_KEY rotations.
MFA_ENCRYPTION_KEY=replace-with-a-generated-fernet-key
GOOGLE_OAUTH_CLIENT_ID=replace-with-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=replace-with-google-oauth-client-secret
GOOGLE_OAUTH_REDIRECT_URI=https://ems.example.com/api/auth/google/callback/
# Optional; leave empty to allow any Google email verified by Google.
GOOGLE_OAUTH_ALLOWED_DOMAIN=example.com
```

`SUPABASE_DB_URL` makes Django use Supabase Postgres as its primary database. Keep the database password private and URL-encode reserved characters. Existing `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` settings remain supported; without either configuration, local development uses SQLite.

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
