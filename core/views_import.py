"""Bulk employee import from Excel (T13+T14).

Admin-only endpoint kept in its own module so ``api/urls.py`` stays
parent-owned. The parent wires :data:`import_urls` into the API router.
"""

import logging
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.urls import path
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Department, Employee
from .supabase_client import supabase

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


def _rollback_supabase_user(created_user_id):
    try:
        supabase.auth.admin.delete_user(created_user_id)
    except Exception:
        logger.exception(
            "import: unable to roll back Supabase user %s", created_user_id
        )


def _commit_rows(validated):
    """Create Supabase users first (per EmployeeListCreateView.post), then
    persist Employee rows with bulk_create. Per-row failures are recorded
    and never abort the batch. Returns (created, failed)."""
    created = 0
    failed = []
    pending = []
    for item in validated:
        if not item["ok"]:
            failed.append({"row": item["row"], "error": "; ".join(item["errors"])})
            continue
        row = item["data"]
        created_user_id = None
        try:
            with transaction.atomic():
                record_id = str(uuid.uuid4())
                auth_response = supabase.auth.admin.create_user(
                    {
                        "id": record_id,
                        "email": row["email"],
                        "email_confirm": True,
                        "user_metadata": {
                            "first_name": row["first_name"],
                            "last_name": row["last_name"],
                        },
                    }
                )
                created_user_id = str(auth_response.user.id)
                pending.append(
                    (
                        item["row"],
                        Employee(
                            id=created_user_id,
                            first_name=row["first_name"],
                            last_name=row["last_name"],
                            email=row["email"],
                            role=row["role"] or None,
                            department=item["department"],
                        ),
                    )
                )
        except IntegrityError:
            if created_user_id:
                _rollback_supabase_user(created_user_id)
            logger.warning("import: duplicate employee race for %s", row["email"])
            failed.append(
                {
                    "row": item["row"],
                    "error": "An employee with this email already exists.",
                }
            )
        except Exception as error:
            if created_user_id:
                _rollback_supabase_user(created_user_id)
            logger.warning(
                "import: unable to create employee row %s: %s", item["row"], error
            )
            failed.append(
                {
                    "row": item["row"],
                    "error": "Unable to create employee upstream. Try again later.",
                }
            )
    if pending:
        try:
            Employee.objects.bulk_create([employee for _, employee in pending])
            created = len(pending)
        except IntegrityError:
            # A duplicate landed after validation: fall back to per-row
            # saves so one conflict never aborts the batch.
            for lineno, employee in pending:
                try:
                    with transaction.atomic():
                        employee.save()
                    created += 1
                except IntegrityError:
                    failed.append(
                        {
                            "row": lineno,
                            "error": (
                                "An employee with this email already exists."
                            ),
                        }
                    )
    return created, failed


class EmployeeImportView(APIView):
    permission_classes = [IsAdminUser]
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
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        validated = _validate_rows(data)
        dry_run = (
            str(request.query_params.get("dry_run", ""))
            .strip()
            .lower()
            in DRY_RUN_TRUE_WORDS
        )
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "rows": [
                        {"row": item["row"], "ok": item["ok"], "errors": item["errors"]}
                        for item in validated
                    ],
                }
            )
        created, failed = _commit_rows(validated)
        return Response({"created": created, "failed": failed})


import_urls = [
    path(
        "settings/import-employees/",
        EmployeeImportView.as_view(),
        name="settings-employee-import",
    ),
]
