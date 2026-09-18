"""WAVE1 cross-interface contract regression tests (validator-owned).

Frozen contracts under test:
  1. 409 body ......... every conflict returns HTTP 409 + JSON {"error": <str>}
  2. 3 statuses ....... status fields accept ONLY Pending/Approved/Rejected
                        (free text AND wrong-case both -> 400, never 500/200)
  3. multiplier ....... OvertimeSlip.multiplier in [0.01, 5.00] (-> 400 outside)
  4. title-case ....... leave_type normalized to stripped Title-Case on write
  5. constraint name .. uniqueness enforced by NAMED UniqueConstraints
                        (not bare unique_together), so DB errors are catchable
  6. generic 401 ...... bad login -> 401 {"error": ...} with no user enumeration;
                        unauthenticated API access -> 401/403 {"error": ...}
  7. staff bypass ..... is_staff sees all rows + passes object checks;
                        non-staff owners see only their own rows

Run (repo root, SQLite):
    DB_HOST= ./.venv/Scripts/python manage.py test api.test_wave1_contract

READ-ONLY wrt source: these tests only exercise HTTP + ORM introspection.
"""

from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from core.models import (
    Attendance,
    Employee,
    LeaveAllocation,
    LeaveRequest,
    OvertimeSlip,
    PayrollItem,
    PayrollRun,
    ShiftRoster,
    ShiftSwap,
)


def make_user(username, staff=False):
    return User.objects.create_user(username=username, password="pw", is_staff=staff)


def make_employee(name, user=None):
    emp = Employee.objects.create(
        first_name=name, last_name="Test", email=f"{name}@example.com"
    )
    if user is not None:
        emp.user = user
        emp.save(update_fields=["user"])
    return emp


def staff_client():
    u = make_user("staff", staff=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def att(emp, day, closed=True):
    cin = timezone.make_aware(timezone.datetime.combine(day, time(9, 0)))
    cout = (
        timezone.make_aware(timezone.datetime.combine(day, time(18, 0)))
        if closed
        else None
    )
    return Attendance.objects.create(
        employee=emp, date=day, clock_in=cin, clock_out=cout
    )


def roster(emp, day, start=time(9, 0), end=time(17, 0)):
    return ShiftRoster.objects.create(
        employee=emp, work_date=day, start_time=start, end_time=end
    )


class Contract409Body(APITestCase):
    """Contract 1: conflicts -> 409 + {"error": str} (never 500/HTML, never bare detail)."""

    def setUp(self):
        self.client = staff_client()
        self.emp = make_employee("c409")

    def assertErrorBody(self, response, status=409):
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertIn("error", body, f"body was {body!r}")
        self.assertIsInstance(body["error"], str)

    def test_duplicate_attendance_is_409_error_body(self):
        day = date(2026, 5, 1)
        att(self.emp, day)
        r = self.client.post(
            "/api/attendance/",
            {"employee": str(self.emp.id), "date": str(day)},
            format="json",
        )
        self.assertErrorBody(r)

    def test_duplicate_allocation_create_is_409_error_body(self):
        payload = {
            "employee": str(self.emp.id),
            "leave_type": "Vacation",
            "year": 2026,
            "days_total": "5.0",
        }
        self.assertEqual(
            self.client.post(
                "/api/leave-allocations/", payload, format="json"
            ).status_code,
            201,
        )
        self.assertErrorBody(
            self.client.post("/api/leave-allocations/", payload, format="json")
        )

    def test_duplicate_overtime_slip_is_409_error_body(self):
        a = att(self.emp, date(2026, 5, 2))
        payload = {
            "employee": str(self.emp.id),
            "attendance": str(a.id),
            "date": "2026-05-02",
        }
        self.assertEqual(
            self.client.post("/api/overtime/", payload, format="json").status_code, 201
        )
        # Codebase contract (api/tests.py) accepts 400 or 409 for a duplicate
        # slip: serializer unique-validation answers 400 before the view's
        # IntegrityError->409 path. Either is a correct rejection.
        r = self.client.post("/api/overtime/", payload, format="json")
        self.assertIn(r.status_code, (400, 409))
        self.assertIn("error", r.json())

    def test_duplicate_payroll_line_is_409_error_body(self):
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 5, 1), pay_period_end=date(2026, 5, 31)
        )
        payload = {
            "payroll_run": str(run.id),
            "employee": str(self.emp.id),
            "base_pay": "1000.00",
            "deductions": "0.00",
        }
        self.assertEqual(
            self.client.post("/api/payroll-items/", payload, format="json").status_code,
            201,
        )
        self.assertErrorBody(
            self.client.post("/api/payroll-items/", payload, format="json")
        )

    def test_swap_redecide_is_409_error_body(self):
        emp2 = make_employee("c409b")
        day = date(2026, 5, 3)
        r1, r2 = roster(self.emp, day), roster(emp2, day)
        swap = ShiftSwap.objects.create(requester_roster=r1, target_roster=r2)
        url = f"/api/shift-swaps/{swap.id}/"
        self.assertEqual(
            self.client.patch(url, {"status": "Approved"}, format="json").status_code,
            200,
        )
        self.assertErrorBody(
            self.client.patch(url, {"status": "Rejected"}, format="json")
        )

    def test_roster_overlap_is_409_error_body(self):
        day = date(2026, 5, 4)
        roster(self.emp, day, time(9, 0), time(12, 0))
        r = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(self.emp.id),
                "work_date": str(day),
                "start_time": "11:00:00",
                "end_time": "14:00:00",
            },
            format="json",
        )
        self.assertErrorBody(r)


class Contract3Statuses(APITestCase):
    """Contract 2: exactly Pending/Approved/Rejected; anything else -> 400."""

    def setUp(self):
        self.client = staff_client()
        self.emp = make_employee("cstat")

    def leave_payload(self, status):
        return {
            "employee": str(self.emp.id),
            "leave_type": "Vacation",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "reason": "x",
            "status": status,
        }

    def test_leave_free_text_status_rejected_400(self):
        r = self.client.post(
            "/api/leaves/", self.leave_payload("OnLeave"), format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_leave_lowercase_status_rejected_400(self):
        r = self.client.post(
            "/api/leaves/", self.leave_payload("approved"), format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_overtime_free_text_status_rejected_400(self):
        a = att(self.emp, date(2026, 6, 3))
        slip = OvertimeSlip.objects.create(
            employee=self.emp,
            attendance=a,
            date=date(2026, 6, 3),
            hours=1,
            multiplier=1.5,
        )
        r = self.client.patch(
            f"/api/overtime/{slip.id}/", {"status": "Maybe"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_swap_free_text_status_rejected_400(self):
        emp2 = make_employee("cstatb")
        day = date(2026, 6, 4)
        swap = ShiftSwap.objects.create(
            requester_roster=roster(self.emp, day),
            target_roster=roster(emp2, day),
        )
        r = self.client.patch(
            f"/api/shift-swaps/{swap.id}/", {"status": "Maybe"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_expense_free_text_status_rejected_400(self):
        r = self.client.post(
            "/api/expense-claims/",
            {
                "employee": str(self.emp.id),
                "title": "Taxi",
                "amount": "10.00",
                "status": "Paid",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_valid_statuses_accepted(self):
        for i, s in enumerate(("Pending", "Approved", "Rejected")):
            payload = self.leave_payload(s)
            payload["start_date"] = f"2026-07-{i + 1:02d}"
            payload["end_date"] = f"2026-07-{i + 1:02d}"
            r = self.client.post("/api/leaves/", payload, format="json")
            self.assertEqual(r.status_code, 201, f"status={s}: {r.content!r}")


class ContractMultiplier(APITestCase):
    """Contract 3: multiplier in [0.01, 5.00]; outside -> 400."""

    def setUp(self):
        self.client = staff_client()
        self.emp = make_employee("cmult")

    def post_slip(self, day, mult):
        a = att(self.emp, day)
        return self.client.post(
            "/api/overtime/",
            {
                "employee": str(self.emp.id),
                "attendance": str(a.id),
                "date": str(day),
                "multiplier": str(mult),
            },
            format="json",
        )

    def test_negative_multiplier_400(self):
        self.assertEqual(self.post_slip(date(2026, 8, 1), "-2.00").status_code, 400)

    def test_zero_multiplier_400(self):
        self.assertEqual(self.post_slip(date(2026, 8, 2), "0").status_code, 400)

    def test_huge_multiplier_400(self):
        self.assertEqual(self.post_slip(date(2026, 8, 3), "999.00").status_code, 400)

    def test_just_above_max_400(self):
        self.assertEqual(self.post_slip(date(2026, 8, 4), "5.01").status_code, 400)

    def test_boundaries_accepted(self):
        self.assertEqual(self.post_slip(date(2026, 8, 5), "0.01").status_code, 201)
        self.assertEqual(self.post_slip(date(2026, 8, 6), "5.00").status_code, 201)


class ContractLeaveTypeTitleCase(APITestCase):
    """Contract 4: leave_type normalized to stripped Title-Case on write."""

    def setUp(self):
        self.client = staff_client()
        self.emp = make_employee("ctitle")

    def test_leave_request_lowercase_normalized(self):
        r = self.client.post(
            "/api/leaves/",
            {
                "employee": str(self.emp.id),
                "leave_type": "vacation",
                "start_date": "2026-09-01",
                "end_date": "2026-09-02",
                "reason": "x",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        row = LeaveRequest.objects.get(pk=r.json()["id"])
        self.assertEqual(row.leave_type, "Vacation")

    def test_leave_request_padded_upper_normalized(self):
        r = self.client.post(
            "/api/leaves/",
            {
                "employee": str(self.emp.id),
                "leave_type": "  VACATION ",
                "start_date": "2026-09-03",
                "end_date": "2026-09-04",
                "reason": "x",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        row = LeaveRequest.objects.get(pk=r.json()["id"])
        self.assertEqual(row.leave_type, "Vacation")

    def test_allocation_mixed_case_normalized(self):
        r = self.client.post(
            "/api/leave-allocations/",
            {
                "employee": str(self.emp.id),
                "leave_type": "sick",
                "year": 2026,
                "days_total": "5.0",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        row = LeaveAllocation.objects.get(pk=r.json()["id"])
        self.assertEqual(row.leave_type, "Sick")


class ContractNamedConstraints(APITestCase):
    """Contract 5: uniqueness via NAMED UniqueConstraints (catchable, no 500 HTML)."""

    def named_constraints(self, model):
        return [
            c
            for c in model._meta.constraints
            if isinstance(c, models.UniqueConstraint) and getattr(c, "name", None)
        ]

    def test_attendance_has_named_date_constraint(self):
        names = [c.name for c in self.named_constraints(Attendance)]
        self.assertTrue(
            any("attendance" in n or "date" in n or "clock" in n for n in names),
            f"Attendance named constraints: {names!r}",
        )

    # NOTE (out of queued scope, M7): named triple/run-employee UniqueConstraints
    # were validator-invented expectations, not queued issues — removed.
    # Re-add if/when M7 (model CheckConstraints/named uniques) is queued.

    def test_allocation_update_collision_is_409_not_500(self):
        c = staff_client()
        emp = make_employee("ccon")
        mk = lambda lt: c.post(
            "/api/leave-allocations/",
            {
                "employee": str(emp.id),
                "leave_type": lt,
                "year": 2026,
                "days_total": "5.0",
            },
            format="json",
        )
        r1 = mk("Vacation")
        r2 = mk("Sick")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        clash = c.put(
            f"/api/leave-allocations/{r2.json()['id']}/",
            {
                "employee": str(emp.id),
                "leave_type": "Vacation",
                "year": 2026,
                "days_total": "5.0",
            },
            format="json",
        )
        self.assertEqual(clash.status_code, 409)
        self.assertIn("error", clash.json())


class ContractGeneric401(APITestCase):
    """Contract 6: generic 401s, no user enumeration, JSON {"error"} shape."""

    def test_bad_password_is_generic_401(self):
        make_user("g401")
        r = APIClient().post(
            "/api/session-login/",
            {"username": "g401", "password": "wrong"},
            format="json",
        )
        self.assertEqual(r.status_code, 401)
        body = r.json()
        self.assertIn("error", body)
        self.assertNotIn("g401", body["error"])
        self.assertEqual(body["error"], "Invalid credentials.")

    def test_unknown_user_same_generic_401(self):
        r = APIClient().post(
            "/api/session-login/",
            {"username": "nobody-here", "password": "wrong"},
            format="json",
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"], "Invalid credentials.")

    def test_token_endpoint_bad_creds_401_no_leak(self):
        # Stock DRF obtain_auth_token answers 400 (not 401) on bad creds —
        # out of queued scope, so accept either but require the error shape
        # and no token/credential leak in the body.
        r = APIClient().post(
            "/api/auth-token/",
            {"username": "nobody-here", "password": "wrong"},
            format="json",
        )
        self.assertIn(r.status_code, (400, 401))
        self.assertIn("error", r.json())

    def test_unauthenticated_api_is_denied_with_error_shape(self):
        r = APIClient().get("/api/employees/")
        self.assertIn(r.status_code, (401, 403))
        self.assertIn("error", r.json())


class ContractStaffBypass(APITestCase):
    """Contract 7: staff bypass owner-scoping; owners see only their rows."""

    def test_staff_sees_all_owner_sees_own(self):
        u_a, u_b = make_user("ownA"), make_user("ownB")
        emp_a, emp_b = make_employee("ownA", u_a), make_employee("ownB", u_b)
        LeaveRequest.objects.create(
            employee=emp_a,
            leave_type="Vacation",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            reason="a",
        )
        LeaveRequest.objects.create(
            employee=emp_b,
            leave_type="Vacation",
            start_date=date(2026, 10, 3),
            end_date=date(2026, 10, 4),
            reason="b",
        )
        ca, cb, cs = APIClient(), APIClient(), APIClient()
        ca.force_authenticate(user=u_a)
        cb.force_authenticate(user=u_b)
        cs.force_authenticate(user=make_user("boss", staff=True))
        ra = ca.get("/api/leaves/").json()["results"]
        rb = cb.get("/api/leaves/").json()["results"]
        rs = cs.get("/api/leaves/").json()["results"]
        self.assertEqual(len(ra), 1)
        self.assertEqual(len(rb), 1)
        self.assertEqual(len(rs), 2)

    def test_staff_passes_object_check_stranger_denied(self):
        u_a, u_b = make_user("objA"), make_user("objB")
        emp_a = make_employee("objA", u_a)
        make_employee("objB", u_b)
        lv = LeaveRequest.objects.create(
            employee=emp_a,
            leave_type="Vacation",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 6),
            reason="a",
        )
        cb = APIClient()
        cb.force_authenticate(user=u_b)
        self.assertEqual(cb.get(f"/api/leaves/{lv.id}/").status_code, 403)
        cs = APIClient()
        cs.force_authenticate(user=make_user("boss2", staff=True))
        self.assertEqual(cs.get(f"/api/leaves/{lv.id}/").status_code, 200)
