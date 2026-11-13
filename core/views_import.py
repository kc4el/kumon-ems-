"""Bulk employee import from Excel (T13+T14).

HR-only endpoint kept in its own module so ``api/urls.py`` stays
parent-owned. The parent wires :data:`import_urls` into the API router.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.urls import path
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Department, Employee
from .permissions import IsStaffOrHR
from .views_onboarding import provision_employee

logger = logging.getLogger(__name__)

COLUMNS = ("first_name", "last_name", "email", "role", "department")

DRY_RUN_TRUE_WORDS = ("1", "true", "yes", "y", "on")


def _cell(value):
    if value is None:
        return ""
    return str(value).strip()


def _parse_workbook(upload):
    """Return [(excel_row_number, {column: value})] or raise ValueError."""
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(upload, read_only=True, data_only=True)
    except Exception:
        raise ValueError("Upload is not a valid .xlsx workbook.")
    rows = list(workbook.active.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Workbook is empty.")
    header = [_cell(value).lower() for value in rows[0]]
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}.")
    index = {column: header.index(column) for column in COLUMNS}
    data = []
    for lineno, raw in enumerate(rows[1:], start=2):
        raw = list(raw) + [None] * max(0, len(header) - len(raw))
        row = {column: _cell(raw[index[column]]) for column in COLUMNS}
        if any(row.values()):
            data.append((lineno, row))
    return data


def _validate_rows(data):
    """Return per-row dicts with row/ok/errors plus resolved internals."""
    dept_map = {dept.name.lower(): dept for dept in Department.objects.all()}
    db_emails = {
        email.lower() for email in Employee.objects.values_list("email", flat=True)
    }
    seen = set()
    validated = []
    for lineno, row in data:
        errors = []
        if not row["first_name"]:
            errors.append("first_name is required.")
        if not row["last_name"]:
            errors.append("last_name is required.")
        email = row["email"]
        if not email:
            errors.append("email is required.")
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                errors.append("Enter a valid email address.")
            else:
                key = email.lower()
                if key in db_emails:
                    errors.append("An employee with this email already exists.")
                elif key in seen:
                    errors.append("Duplicate email within this sheet.")
        dept_name = row["department"]
        department = None
        if dept_name:
            department = dept_map.get(dept_name.lower())
            if department is None:
                errors.append(f"Unknown department: {dept_name}.")
        ok = not errors
        if ok and email:
            seen.add(email.lower())
        validated.append(
            {
                "row": lineno,
                "ok": ok,
                "errors": errors,
                "data": row,
                "department": department,
            }
        )
    return validated


def _commit_rows(validated, actor_id):
    """Provision each valid row independently, returning credentials on success."""
    credentials = []
    failed = []
    for item in validated:
        if not item["ok"]:
            failed.append({"row": item["row"], "error": "; ".join(item["errors"])})
            continue
        row = item["data"]
        try:
            result = provision_employee(
                first_name=row["first_name"], last_name=row["last_name"],
                email=row["email"], role=row["role"], department=item["department"],
                date_hired=timezone.localdate(), actor_id=actor_id,
            )
            credentials.append({"row": item["row"], **result})
        except IntegrityError:
            failed.append(
                {
                    "row": item["row"],
                    "error": "Employee creation conflicted with an existing record.",
                }
            )
        except DjangoValidationError:
            failed.append({"row": item["row"], "error": "Employee data is invalid."})
        except Exception:
            logger.warning("import: unable to create employee row %s", item["row"])
            failed.append(
                {
                    "row": item["row"],
                    "error": "Unable to create employee. Try again later.",
                }
            )
    return len(credentials), failed, credentials


class EmployeeImportView(APIView):
    permission_classes = [IsStaffOrHR]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"error": "An .xlsx file upload named 'file' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            data = _parse_workbook(upload)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        validated = _validate_rows(data)
        dry_run = (
            str(request.query_params.get("dry_run", "")).strip().lower()
            in DRY_RUN_TRUE_WORDS
        )
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "rows": [
                        {
                            "row": item["row"],
                            "ok": item["ok"],
                            "errors": item["errors"],
                            **item["data"],
                        }
                        for item in validated
                    ],
                }
            )
        created, failed, credentials = _commit_rows(validated, request.user.pk)
        response = Response({"created": created, "failed": failed, "credentials": credentials})
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response


import_urls = [
    path(
        "settings/import-employees/",
        EmployeeImportView.as_view(),
        name="settings-employee-import",
    ),
]
