"""Isolated checks that do not import Django or initialize application services."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def extract_function(filename, name, class_name=None):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    nodes = tree.body
    if class_name:
        nodes = next(node.body for node in nodes if isinstance(node, ast.ClassDef) and node.name == class_name)
    function = next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    return compile(module, filename, "exec")


class IsolatedImportTests(unittest.TestCase):
    def test_commit_continues_after_failure_and_only_returns_success_credentials(self):
        class IntegrityError(Exception):
            pass

        class ValidationError(Exception):
            pass

        provision = Mock(side_effect=[RuntimeError("failure"), {"employee_id": "EMP-1", "temporary_password": "secret"}])
        namespace = {
            "provision_employee": provision,
            "IntegrityError": IntegrityError,
            "DjangoValidationError": ValidationError,
            "timezone": SimpleNamespace(localdate=lambda: "today"),
            "logger": Mock(),
        }
        exec(extract_function("core/views_import.py", "_commit_rows"), namespace)
        row = {"first_name": "A", "last_name": "B", "email": "a@example.com", "role": ""}
        items = [
            {"row": 2, "ok": True, "data": row, "department": None},
            {"row": 3, "ok": True, "data": row, "department": None},
        ]
        created, failed, credentials = namespace["_commit_rows"](items, 7)
        self.assertEqual(created, 1)
        self.assertEqual(failed[0]["row"], 2)
        self.assertEqual(credentials, [{"row": 3, "employee_id": "EMP-1", "temporary_password": "secret"}])
        self.assertEqual(provision.call_count, 2)
        self.assertNotIn("secret", str(namespace["logger"].mock_calls))

    def test_impossible_hire_date_returns_400_before_database_access(self):
        def parse_date(value):
            raise ValueError("day is out of range")

        response = Mock(side_effect=lambda data, status: (data, status))
        namespace = {"parse_date": parse_date, "Response": response}
        exec(extract_function("core/views_onboarding.py", "post", "OnboardEmployeeView"), namespace)
        request = SimpleNamespace(data={
            "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com",
            "date_hired": "2026-02-30",
        })
        result = namespace["post"](None, request)
        self.assertEqual(result[1], 400)
        self.assertIn("valid start date", result[0]["error"])


if __name__ == "__main__":
    unittest.main()
