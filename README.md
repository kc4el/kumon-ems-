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
