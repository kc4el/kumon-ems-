"""Run isolated request integrity checks without importing Django or the app."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]


class Response:
    def __init__(self, data=None, status=200):
        self.data, self.status_code = data, status


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


class Row:
    def __init__(self, state="Pending"):
        self.pk = uuid.uuid4()
        self.status = state
        self.employee = object()
        self.leave_type = "Vacation"
        self.start_date = self.end_date = "2026-12-01"
        self.saves = 0

    def save(self, **kwargs):
        self.saves += 1


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select_for_update(self):
        return self

    def all(self):
        return self

    def filter(self, pk__in):
        return Query([row for row in self.rows if row.pk in pk__in])

    def order_by(self, field):
        return sorted(self.rows, key=lambda row: row.pk)


class Base:
    def get_object(self):
        return self.obj

    def get_serializer(self, obj):
        return SimpleNamespace(data={"status": obj.status})

    def perform_destroy(self, obj):
        obj.deleted = True


def load_classes(filename, names, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    assert len(nodes) == len(names)
    for node in nodes:
        node.bases = [ast.Name(id="Base", ctx=ast.Load())]
        for method in node.body:
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(filename), "exec"), namespace)


def environment(rows):
    query = Query(rows)
    log = SimpleNamespace(create=lambda **kwargs: None)
    return {
        "Base": Base, "APIView": Base, "uuid": uuid, "Response": Response,
        "status": SimpleNamespace(HTTP_200_OK=200, HTTP_204_NO_CONTENT=204, HTTP_400_BAD_REQUEST=400, HTTP_409_CONFLICT=409),
        "transaction": SimpleNamespace(atomic=nullcontext),
        "LeaveRequest": SimpleNamespace(objects=query),
        "SalaryAdvance": SimpleNamespace(objects=query),
        "SalaryAdvanceSerializer": object,
        "LeaveRequestSerializer": lambda row: SimpleNamespace(data={"status": row.status}),
        "EmployeeAuditLog": SimpleNamespace(objects=log),
        "get_object_or_404": lambda manager, pk: next(r for r in manager.rows if r.pk == pk),
        "IsStaffOrHR": object, "IsAuthenticated": object, "IsOwnerOrStaff": object,
        "is_staff_or_hr": lambda user: user == "hr",
        "PermissionDenied": Invalid, "DRFValidationError": Invalid,
        "Conflict409": Conflict, "DECISION_CHOICES": ("Approved", "Rejected"),
    }


class IntegrityProbe(unittest.TestCase):
    def setUp(self):
        self.pending, self.approved = Row(), Row("Approved")
        self.env = environment([self.pending, self.approved])
        load_classes("core/views_actions.py", {"LeaveApproveView", "LeaveRejectView", "LeaveBulkDecideView"}, self.env)
        load_classes("core/views.py", {"LeaveRequestDetailView"}, self.env)
        load_classes("core/views_docs.py", {"SalaryAdvanceDetailView"}, self.env)

    def request(self, data=None):
        return SimpleNamespace(data=data or {}, user="hr")

    def test_action_replays_and_conflicts(self):
        approve = self.env["LeaveApproveView"]()
        reject = self.env["LeaveRejectView"]()
        self.assertEqual(approve.post(self.request(), self.pending.pk).status_code, 200)
        self.assertEqual(approve.post(self.request(), self.pending.pk).status_code, 200)
        self.assertEqual(reject.post(self.request(), self.pending.pk).status_code, 409)
        self.assertEqual(self.pending.saves, 1)
        rejected = Row("Rejected")
        self.env["LeaveRequest"].objects.rows.append(rejected)
        self.assertEqual(reject.post(self.request(), rejected.pk).status_code, 200)
        self.assertEqual(approve.post(self.request(), rejected.pk).status_code, 409)
        self.assertEqual(rejected.saves, 0)

    def test_bulk_conflict_and_invalid_inputs_leave_all_rows_unchanged(self):
        bulk = self.env["LeaveBulkDecideView"]()
        ids = [str(self.pending.pk), str(self.approved.pk)]
        for data in (
            {"ids": ids, "decision": "Rejected"},
            {"ids": ids, "decision": []},
            {"ids": ["bad"], "decision": "Approved"},
            {"ids": [str(uuid.uuid4())], "decision": "Approved"},
        ):
            self.assertIn(bulk.post(self.request(data)).status_code, (400, 409))
            self.assertEqual(self.pending.status, "Pending")
            self.assertEqual(self.pending.saves, 0)
        self.assertEqual(bulk.post(self.request({"ids": ids, "decision": "Approved"})).status_code, 200)
        self.assertEqual(self.pending.saves, 1)
        self.assertEqual(self.approved.saves, 0)

    def test_final_detail_edits_and_deletes_fail(self):
        for name in ("LeaveRequestDetailView", "SalaryAdvanceDetailView"):
            view = self.env[name]()
            view.queryset = Query([self.approved])
            view.obj = self.approved
            with self.subTest(view=name):
                with self.assertRaises(Conflict):
                    view.update(self.request({"reason": "changed"}))
                with self.assertRaises(Conflict):
                    view.destroy(self.request())
                self.assertFalse(hasattr(self.approved, "deleted"))


if __name__ == "__main__":
    unittest.main()
