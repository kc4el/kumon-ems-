"""T13+T14: Excel employee import endpoint tests (own file).

Builds .xlsx workbooks in memory with openpyxl. Self-wires the import
route (parent owns api/urls.py) via a test-only URLconf.
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import include, path
from rest_framework.test import APIClient

from core.models import Department, Employee
from core.views_import import import_urls

urlpatterns = [
    path("api/", include("api.urls")),
    path("api/", include(import_urls)),
]

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["first_name", "last_name", "email", "role", "department"]
URL = "/api/settings/import-employees/"


def xlsx_file(rows, name="employees.xlsx"):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=XLSX_CT)


def _supa_users(*ids):
    return [SimpleNamespace(user=SimpleNamespace(id=i)) for i in ids]


@override_settings(ROOT_URLCONF="api.test_settings_import")
class EmployeeImportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin = User.objects.create_user(username="boss", password="x", is_staff=True)
        self.client.force_authenticate(admin)
        self.dept = Department.objects.create(name="Engineering", code="ENG")

    def test_valid_sheet_dry_run_all_ok_and_writes_nothing(self):
        upload = xlsx_file(
            [
                ["Ada", "Lovelace", "ada@example.com", "Engineer", "engineering"],
                ["Grace", "Hopper", "grace@example.com", "Lead", "Engineering"],
            ]
        )
        r = self.client.post(URL + "?dry_run=1", {"file": upload}, format="multipart")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["dry_run"])
        self.assertEqual(len(body["rows"]), 2)
        for item in body["rows"]:
            self.assertTrue(item["ok"], item)
            self.assertEqual(item["errors"], [])
        self.assertEqual(Employee.objects.count(), 0)

    def test_dup_and_bad_sheet_row_errors(self):
        Employee.objects.create(
            first_name="Old", last_name="Timer", email="dup@example.com"
        )
        upload = xlsx_file(
            [
                ["New", "Hire", "DUP@example.com", "", ""],  # row 2: DB duplicate
                ["A", "One", "twin@example.com", "", ""],  # row 3: ok at first sight
                ["B", "Two", "TWIN@example.com", "", ""],  # row 4: within-sheet dup
                ["", "Noname", "noname@example.com", "", ""],  # row 5: blank name
                ["Bad", "Email", "not-an-email", "", ""],  # row 6: bad email
                ["Lost", "Soul", "lost@example.com", "", "Nope"],  # row 7: bad dept
                ["Good", "Guy", "good@example.com", "Dev", "Engineering"],  # row 8: ok
            ]
        )
        r = self.client.post(URL + "?dry_run=1", {"file": upload}, format="multipart")
        self.assertEqual(r.status_code, 200)
        by_row = {item["row"]: item for item in r.json()["rows"]}
        self.assertFalse(by_row[2]["ok"])
        self.assertTrue(
            any("already exists" in e for e in by_row[2]["errors"]), by_row[2]
        )
        self.assertTrue(by_row[3]["ok"], by_row[3])
        self.assertFalse(by_row[4]["ok"])
        self.assertTrue(
            any("within this sheet" in e for e in by_row[4]["errors"]), by_row[4]
        )
        self.assertFalse(by_row[5]["ok"])
        self.assertTrue(any("first_name" in e for e in by_row[5]["errors"]), by_row[5])
        self.assertFalse(by_row[6]["ok"])
        self.assertTrue(any("valid email" in e for e in by_row[6]["errors"]), by_row[6])
        self.assertFalse(by_row[7]["ok"])
        self.assertTrue(
            any("Unknown department" in e for e in by_row[7]["errors"]), by_row[7]
        )
        self.assertTrue(by_row[8]["ok"], by_row[8])
        # Dry run writes nothing: only the pre-seeded row exists.
        self.assertEqual(Employee.objects.count(), 1)

    @patch("core.views_import.supabase")
    def test_commit_path_three_good_one_bad(self, supabase):
        supabase.auth.admin.create_user.side_effect = _supa_users(
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
            "33333333-3333-4333-8333-333333333333",
        )
        upload = xlsx_file(
            [
                ["Ada", "Lovelace", "ada@example.com", "Engineer", "Engineering"],
                ["Grace", "Hopper", "grace@example.com", "", ""],
                ["Alan", "Turing", "alan@example.com", "Scientist", "engineering"],
                ["Bad", "Email", "not-an-email", "", ""],
            ]
        )
        r = self.client.post(URL, {"file": upload}, format="multipart")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["created"], 3)
        self.assertEqual(len(body["failed"]), 1)
        self.assertEqual(body["failed"][0]["row"], 5)
        self.assertEqual(supabase.auth.admin.create_user.call_count, 3)
        self.assertEqual(Employee.objects.count(), 3)
        ada = Employee.objects.get(email="ada@example.com")
        self.assertEqual(ada.department_id, self.dept.id)
        self.assertEqual(ada.role, "Engineer")
