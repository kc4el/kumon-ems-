"""Scratch authz probes for review-round6 (not part of shipped suite).

Run: DB_HOST= TZ=UTC PYTHONPATH=<repo>/docs/review-round6 \
     ./.venv/Scripts/python manage.py test probes
Each test prints PROBE:<name>:<observation> and asserts the CURRENT
(vulnerable) behaviour so failures mark fixed issues, not bad probes.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Attendance,
    AttendanceCorrection,
    ClaimStatus,
    Department,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
    LeaveAllocation,
    LeaveRequest,
    Message,
    OvertimeSlip,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
    ShiftSwap,
)


def mkuser(name, staff=False):
    return User.objects.create(username=name, is_staff=staff)


def mkemp(tag, user=None):
    e = Employee.objects.create(
        first_name=f"F{tag}", last_name=f"L{tag}", email=f"{tag}@example.com"
    )
    if user is not None:
        e.user = user
        e.save(update_fields=["user"])
    return e


def cli(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class CreateAsOtherProbes(TestCase):
    """POST endpoints accept any employee FK from any authenticated user."""

    def setUp(self):
        self.victim = mkuser("victim")
        self.victim_emp = mkemp("victim", self.victim)
        self.attacker = mkuser("attacker")
        self.attacker_emp = mkemp("attacker", self.attacker)

    def test_leave_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/leaves/",
            {"employee": str(self.victim_emp.id),
             "start_date": "2026-08-24", "end_date": "2026-08-25",
             "reason": "forged"},
            format="json",
        )
        print(f"PROBE:create-leave-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(LeaveRequest.objects.filter(
            employee=self.victim_emp, reason="forged").exists())

    def test_attendance_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/attendance/",
            {"employee": str(self.victim_emp.id), "date": "2026-09-11"},
            format="json",
        )
        print(f"PROBE:create-attendance-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_expense_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/expense-claims/",
            {"employee": str(self.victim_emp.id),
             "title": "forged", "amount": "9.99"},
            format="json",
        )
        print(f"PROBE:create-expense-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_performance_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/performance/",
            {"employee": str(self.victim_emp.id),
             "review_date": "2026-09-01", "score": 1, "comments": "forged"},
            format="json",
        )
        print(f"PROBE:create-performance-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_payroll_item_create_as_other(self):
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 9, 1), pay_period_end=date(2026, 9, 30))
        r = cli(self.attacker).post(
            "/api/payroll-items/",
            {"payroll_run": str(run.id),
             "employee": str(self.victim_emp.id), "base_pay": "100.00"},
            format="json",
        )
        print(f"PROBE:create-payrollitem-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_allocation_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/leave-allocations/",
            {"employee": str(self.victim_emp.id), "leave_type": "Sick",
             "year": 2026, "days_total": "3.0"},
            format="json",
        )
        print(f"PROBE:create-allocation-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_roster_create_as_other(self):
        r = cli(self.attacker).post(
            "/api/shift-rosters/",
            {"employee": str(self.victim_emp.id), "work_date": "2026-09-02",
             "shift_type": "Night", "start_time": "22:00:00",
             "end_time": "23:00:00"},
            format="json",
        )
        print(f"PROBE:create-roster-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_overtime_create_as_other_pair(self):
        att = Attendance.objects.create(
            employee=self.victim_emp, date=date(2026, 9, 12),
            clock_in=timezone.now() - timedelta(hours=10),
            clock_out=timezone.now())
        r = cli(self.attacker).post(
            "/api/overtime/",
            {"employee": str(self.victim_emp.id),
             "attendance": str(att.id), "date": "2026-09-12"},
            format="json",
        )
        print(f"PROBE:create-overtime-as-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_correction_create_on_others_attendance(self):
        base = timezone.make_aware(timezone.datetime(2026, 9, 13, 9, 0))
        att = Attendance.objects.create(
            employee=self.victim_emp, date=date(2026, 9, 13),
            clock_in=base,
            clock_out=base + timedelta(hours=8))
        r = cli(self.attacker).post(
            "/api/attendance-corrections/",
            {"attendance": str(att.id), "reason": "forged fix",
             "proposed_clock_in": "2026-09-13T08:00:00Z"},
            format="json",
        )
        print(f"PROBE:create-correction-on-other:{r.status_code}")
        self.assertEqual(r.status_code, 201)

    def test_swap_create_between_strangers(self):
        ra = ShiftRoster.objects.create(
            employee=self.victim_emp, work_date=date(2026, 9, 3),
            shift_type="A", start_time="09:00:00", end_time="13:00:00")
        rb = ShiftRoster.objects.create(
            employee=self.attacker_emp, work_date=date(2026, 9, 3),
            shift_type="B", start_time="14:00:00", end_time="18:00:00")
        third = mkuser("third")
        mkemp("third", third)
        r = cli(third).post(
            "/api/shift-swaps/",
            {"requester_roster": str(ra.id), "target_roster": str(rb.id)},
            format="json",
        )
        print(f"PROBE:create-swap-as-stranger:{r.status_code}")
        self.assertEqual(r.status_code, 201)


class SelfApprovalProbes(TestCase):
    """Owners can approve/edit their own rows; no staff-only write gate."""

    def setUp(self):
        self.u = mkuser("selfapp")
        self.e = mkemp("selfapp", self.u)

    def test_leave_self_approve(self):
        lv = LeaveRequest.objects.create(
            employee=self.e, start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25), reason="x")
        r = cli(self.u).patch(f"/api/leaves/{lv.id}/",
                              {"status": "Approved"}, format="json")
        print(f"PROBE:leave-self-approve:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        lv.refresh_from_db()
        self.assertEqual(lv.status, "Approved")

    def test_expense_self_approve(self):
        c = ExpenseClaim.objects.create(
            employee=self.e, title="x", amount="5.00")
        r = cli(self.u).patch(f"/api/expense-claims/{c.id}/",
                              {"status": "Approved"}, format="json")
        print(f"PROBE:expense-self-approve:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.status, "Approved")

    def test_overtime_self_approve(self):
        att = Attendance.objects.create(
            employee=self.e, date=date(2026, 9, 14),
            clock_in=timezone.now() - timedelta(hours=10),
            clock_out=timezone.now())
        slip = OvertimeSlip.objects.create(
            employee=self.e, attendance=att, date=date(2026, 9, 14), hours="2.00")
        r = cli(self.u).patch(f"/api/overtime/{slip.id}/",
                              {"status": "Approved"}, format="json")
        print(f"PROBE:overtime-self-approve:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        slip.refresh_from_db()
        self.assertEqual(slip.status, "Approved")

    def test_correction_self_approve_runs_side_effects(self):
        att = Attendance.objects.create(
            employee=self.e, date=date(2026, 9, 15),
            clock_in=timezone.make_aware(timezone.datetime(2026, 9, 15, 9, 0)),
            clock_out=timezone.make_aware(timezone.datetime(2026, 9, 15, 17, 0)))
        cor = AttendanceCorrection.objects.create(
            attendance=att, reason="fix",
            proposed_clock_in=timezone.make_aware(
                timezone.datetime(2026, 9, 15, 8, 0)))
        r = cli(self.u).patch(
            f"/api/attendance-corrections/{cor.id}/",
            {"status": "Approved"}, format="json")
        att.refresh_from_db()
        print(f"PROBE:correction-self-approve:{r.status_code}:"
              f"clock_in={att.clock_in}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(att.clock_in, cor.proposed_clock_in)

    def test_correction_put_status_bypass_no_side_effects(self):
        original_in = timezone.make_aware(timezone.datetime(2026, 9, 16, 9, 0))
        att = Attendance.objects.create(
            employee=self.e, date=date(2026, 9, 16),
            clock_in=original_in,
            clock_out=timezone.make_aware(timezone.datetime(2026, 9, 16, 17, 0)))
        cor = AttendanceCorrection.objects.create(
            attendance=att, reason="fix",
            proposed_clock_in=timezone.make_aware(
                timezone.datetime(2026, 9, 16, 8, 0)))
        r = cli(self.u).put(
            f"/api/attendance-corrections/{cor.id}/",
            {"attendance": str(att.id), "reason": "fix",
             "proposed_clock_in": "2026-09-16T08:00:00Z",
             "proposed_clock_out": "2026-09-16T17:00:00Z",
             "status": "Approved"},
            format="json")
        att.refresh_from_db()
        cor.refresh_from_db()
        print(f"PROBE:correction-put-bypass:{r.status_code}:"
              f"status={cor.status}:applied={att.clock_in == original_in}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cor.status, "Approved")
        self.assertEqual(att.clock_in, original_in)  # never applied

    def test_performance_self_edit(self):
        pr = PerformanceReview.objects.create(
            employee=self.e, review_date=date(2026, 9, 1),
            score=1, comments="bad")
        r = cli(self.u).patch(f"/api/performance/{pr.id}/",
                              {"score": 5, "comments": "great"},
                              format="json")
        print(f"PROBE:performance-self-edit:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        pr.refresh_from_db()
        self.assertEqual(pr.score, 5)

    def test_payroll_self_raise(self):
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 9, 1), pay_period_end=date(2026, 9, 30))
        item = PayrollItem.objects.create(
            payroll_run=run, employee=self.e,
            base_pay="100.00", deductions="0.00", net_pay="100.00")
        r = cli(self.u).patch(f"/api/payroll-items/{item.id}/",
                              {"base_pay": "99999.00"}, format="json")
        item.refresh_from_db()
        print(f"PROBE:payroll-self-raise:{r.status_code}:net={item.net_pay}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(str(item.net_pay), "99999.00")

    def test_roster_self_edit(self):
        ro = ShiftRoster.objects.create(
            employee=self.e, work_date=date(2026, 9, 4),
            shift_type="Day", start_time="09:00:00", end_time="17:00:00")
        r = cli(self.u).patch(f"/api/shift-rosters/{ro.id}/",
                              {"shift_type": "Nap"}, format="json")
        print(f"PROBE:roster-self-edit:{r.status_code}")
        self.assertEqual(r.status_code, 200)

    def test_attendance_direct_edit_bypasses_correction(self):
        att = Attendance.objects.create(
            employee=self.e, date=date(2026, 9, 17),
            clock_in=timezone.make_aware(timezone.datetime(2026, 9, 17, 9, 0)),
            clock_out=timezone.make_aware(timezone.datetime(2026, 9, 17, 17, 0)))
        r = cli(self.u).patch(
            f"/api/attendance/{att.id}/",
            {"clock_in": "2026-09-17T06:00:00Z"}, format="json")
        att.refresh_from_db()
        print(f"PROBE:attendance-direct-edit:{r.status_code}:"
              f"hour={att.clock_in.hour}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(att.clock_in.hour, 6)

    def test_employee_self_deactivate_and_role(self):
        r = cli(self.u).patch(
            f"/api/employees/{self.e.id}/",
            {"role": "Chief", "is_active": False}, format="json")
        self.e.refresh_from_db()
        print(f"PROBE:employee-self-edit:{r.status_code}:"
              f"role={self.e.role}:active={self.e.is_active}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.e.is_active)


class SwapPartyProbes(TestCase):
    def setUp(self):
        self.ua = mkuser("swA")
        self.ea = mkemp("swA", self.ua)
        self.ub = mkuser("swB")
        self.eb = mkemp("swB", self.ub)
        self.day = date(2026, 9, 5)
        self.ra = ShiftRoster.objects.create(
            employee=self.ea, work_date=self.day, shift_type="AM",
            start_time="09:00:00", end_time="13:00:00")
        self.rb = ShiftRoster.objects.create(
            employee=self.eb, work_date=self.day, shift_type="PM",
            start_time="14:00:00", end_time="18:00:00")

    def _swap(self):
        return ShiftSwap.objects.create(
            requester_roster=self.ra, target_roster=self.rb)

    def test_requester_self_approves_own_swap(self):
        sw = self._swap()
        r = cli(self.ua).patch(f"/api/shift-swaps/{sw.id}/",
                               {"status": "Approved"}, format="json")
        self.ra.refresh_from_db()
        print(f"PROBE:swap-self-approve:{r.status_code}:"
              f"holder={self.ra.employee_id == self.eb.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ra.employee_id, self.eb.id)

    def test_stranger_denied(self):
        sw = self._swap()
        outsider = mkuser("swOut")
        mkemp("swOut", outsider)
        r = cli(outsider).patch(f"/api/shift-swaps/{sw.id}/",
                                {"status": "Approved"}, format="json")
        print(f"PROBE:swap-stranger:{r.status_code}")
        self.assertIn(r.status_code, (403, 404))

    def test_post_approval_both_parties_still_see(self):
        sw = self._swap()
        cli(self.ua).patch(f"/api/shift-swaps/{sw.id}/",
                           {"status": "Approved"}, format="json")
        for u, tag in ((self.ua, "A"), (self.ub, "B")):
            ids = [row["id"] for row in
                   cli(u).get("/api/shift-swaps/").json()["results"]]
            print(f"PROBE:swap-visible-{tag}:{str(sw.id) in ids}")
            self.assertIn(str(sw.id), ids)

    def test_null_side_swap_visible_but_unapprovable(self):
        rn = ShiftRoster.objects.create(
            employee=None, work_date=self.day, shift_type="Open",
            start_time="19:00:00", end_time="20:00:00")
        sw = ShiftSwap.objects.create(
            requester_roster=rn, target_roster=self.rb)
        r = cli(self.ub).get(f"/api/shift-swaps/{sw.id}/")
        print(f"PROBE:swap-null-side-detail:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        r2 = cli(self.ub).patch(f"/api/shift-swaps/{sw.id}/",
                                {"status": "Approved"}, format="json")
        print(f"PROBE:swap-null-side-approve:{r2.status_code}")
        self.assertEqual(r2.status_code, 400)


class OvertimeMismatchProbes(TestCase):
    """Slip.employee=A but slip.attendance.employee=B: list vs detail split."""

    def setUp(self):
        self.ua = mkuser("otA")
        self.ea = mkemp("otA", self.ua)
        self.ub = mkuser("otB")
        self.eb = mkemp("otB", self.ub)
        att = Attendance.objects.create(
            employee=self.eb, date=date(2026, 9, 18),
            clock_in=timezone.now() - timedelta(hours=10),
            clock_out=timezone.now())
        self.slip = OvertimeSlip.objects.create(
            employee=self.ea, attendance=att,
            date=date(2026, 9, 18), hours="2.00")

    def test_list_hides_but_detail_allows(self):
        ids = [row["id"] for row in
               cli(self.ub).get("/api/overtime/").json()["results"]]
        d = cli(self.ub).get(f"/api/overtime/{self.slip.id}/")
        print(f"PROBE:ot-mismatch:list={str(self.slip.id) in ids}:"
              f"detail={d.status_code}")
        self.assertNotIn(str(self.slip.id), ids)
        self.assertEqual(d.status_code, 200)


class UnscopedEndpointProbes(TestCase):
    def setUp(self):
        self.u = mkuser("plain")
        self.e = mkemp("plain", self.u)
        self.v = mkuser("vic2")
        self.ve = mkemp("vic2", self.v)

    def test_department_create_and_delete_as_nonstaff(self):
        c = cli(self.u).post(
            "/api/departments/", {"name": "ProbeDeptX", "code": "PDX"},
            format="json")
        print(f"PROBE:dept-create:{c.status_code}")
        self.assertEqual(c.status_code, 201)
        d = cli(self.u).delete(f"/api/departments/{c.json()['id']}/")
        print(f"PROBE:dept-delete:{d.status_code}")
        self.assertIn(d.status_code, (200, 204))

    def test_payroll_run_create_and_delete_as_nonstaff(self):
        c = cli(self.u).post(
            "/api/payroll-runs/",
            {"pay_period_start": "2026-09-01",
             "pay_period_end": "2026-09-30"}, format="json")
        print(f"PROBE:payrollrun-create:{c.status_code}")
        self.assertEqual(c.status_code, 201)
        d = cli(self.u).delete(f"/api/payroll-runs/{c.json()['id']}/")
        print(f"PROBE:payrollrun-delete:{d.status_code}")
        self.assertIn(d.status_code, (200, 204))

    def test_audit_log_list_leaks(self):
        EmployeeAuditLog.objects.create(
            employee=self.ve, action="resigned 2026-01-01")
        r = cli(self.u).get("/api/audit-logs/")
        texts = [row["action"] for row in r.json()["results"]]
        print(f"PROBE:audit-leak:{r.status_code}:"
              f"{any('resigned 2026-01-01' in t for t in texts)}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any("resigned 2026-01-01" in t for t in texts))

    def test_leave_balance_of_other(self):
        LeaveAllocation.objects.create(
            employee=self.ve, leave_type="Sick", year=2026, days_total="7.0")
        r = cli(self.u).get(
            f"/api/leave-balances/?employee={self.ve.id}&year=2026")
        print(f"PROBE:balance-of-other:{r.status_code}:{r.json()}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json()["balances"]["Sick"]["allocated"], 7.0)

    def test_leave_balance_garbage_employee(self):
        with self.assertRaises(Exception):
            cli(self.u).get("/api/leave-balances/?employee=nope&year=2026")
        print("PROBE:balance-garbage:raises-unhandled-500")

    def test_shift_conflict_of_other(self):
        ShiftRoster.objects.create(
            employee=self.ve, work_date=date(2026, 9, 6),
            shift_type="Day", start_time="09:00:00", end_time="17:00:00")
        LeaveRequest.objects.create(
            employee=self.ve, start_date=date(2026, 9, 6),
            end_date=date(2026, 9, 6), reason="x", status="Approved")
        r = cli(self.u).get(
            f"/api/shift-rosters/conflicts/?employee={self.ve.id}"
            f"&date=2026-09-06")
        print(f"PROBE:conflict-of-other:{r.status_code}:{r.json()}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["conflicts"]), 1)

    def test_clock_out_other_employee(self):
        Attendance.objects.create(
            employee=self.ve, date=date(2026, 9, 19),
            clock_in=timezone.now() - timedelta(hours=2))
        r = cli(self.u).post(
            "/api/attendance/clock-out/",
            {"employee_id": str(self.ve.id),
             "clock_out": "2026-09-19T18:00:00Z"}, format="json")
        print(f"PROBE:clockout-other:{r.status_code}")
        self.assertEqual(r.status_code, 200)
        att = Attendance.objects.get(employee=self.ve, date=date(2026, 9, 19))
        self.assertIsNotNone(att.clock_out)

    def test_messages_cross_conversation(self):
        c = cli(self.v).post(
            "/api/messages/",
            {"text": "victim secret", "conversation_key": "conv-victim"},
            format="json")
        print(f"PROBE:message-post:{c.status_code}")
        r = cli(self.u).get("/api/messages/?conversation=conv-victim")
        texts = [row["text"] for row in r.json()["results"]]
        print(f"PROBE:message-cross-read:{r.status_code}:"
              f"{'victim secret' in texts}")
        self.assertIn("victim secret", texts)

    def test_claim_status_hijack(self):
        cli(self.v).post(
            "/api/claim-statuses/",
            {"claim_id": "PROBE9", "status": "Pending"}, format="json")
        r = cli(self.u).post(
            "/api/claim-statuses/",
            {"claim_id": "PROBE9", "status": "Approved"}, format="json")
        print(f"PROBE:claim-hijack:{r.status_code}:"
              f"{ClaimStatus.objects.get(claim_id='PROBE9').status}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            ClaimStatus.objects.get(claim_id="PROBE9").status, "Approved")

    @patch("core.views.supabase")
    def test_employee_create_as_nonstaff_mints_row(self, supabase):
        from types import SimpleNamespace
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="55555555-5555-4555-8555-555555555555"))
        r = cli(self.u).post(
            "/api/employees/",
            {"first_name": "Mint", "last_name": "Ed",
             "email": "minted@example.com", "password": "Sup3rSecret!",
             "role": "Manager"},
            format="json")
        print(f"PROBE:employee-mint:{r.status_code}")
        self.assertEqual(r.status_code, 201)
        row = Employee.objects.get(email="minted@example.com")
        print(f"PROBE:employee-mint-role:{row.role}:"
              f"user={row.user is not None}")
        self.assertEqual(row.role, "Manager")
        self.assertIsNotNone(row.user)


class UnlinkedUserProbes(TestCase):
    """User with no Employee row: ghost with write-only access."""

    def setUp(self):
        self.v = mkuser("ghostvic")
        self.ve = mkemp("ghostvic", self.v)
        self.ghost = mkuser("ghost")

    def test_ghost_create_read_asymmetry(self):
        c = cli(self.ghost).post(
            "/api/leaves/",
            {"employee": str(self.ve.id), "start_date": "2026-08-24",
             "end_date": "2026-08-25", "reason": "ghost-write"},
            format="json")
        lv = LeaveRequest.objects.filter(reason="ghost-write").first()
        lst = cli(self.ghost).get("/api/leaves/").json()["results"]
        d = (cli(self.ghost).get(f"/api/leaves/{lv.id}/").status_code
             if lv else None)
        print(f"PROBE:ghost:create={c.status_code}:"
              f"list_sees={len(lst)}:detail={d}")
        self.assertEqual(c.status_code, 201)
        self.assertEqual(lst, [])
        self.assertIn(d, (403, 404))

    def test_ghost_employee_list_empty(self):
        r = cli(self.ghost).get("/api/employees/").json()["results"]
        print(f"PROBE:ghost-employee-list:{len(r)}")
        self.assertEqual(r, [])


class OrphanLinkProbes(TestCase):
    @patch("core.views.supabase")
    def test_anonymous_signup_without_password_leaves_orphan(self, supabase):
        from types import SimpleNamespace
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="66666666-6666-4666-8666-666666666666"))
        anon = APIClient()
        r = anon.post(
            "/api/employees/",
            {"first_name": "No", "last_name": "Pwd",
             "email": "nopwd@example.com"},
            format="json")
        row = Employee.objects.get(email="nopwd@example.com")
        print(f"PROBE:signup-no-pwd:{r.status_code}:user={row.user}")
        self.assertEqual(r.status_code, 202)
        self.assertIsNone(row.user)

    def test_backfill_ignores_username_only_user(self):
        from core.migrations_compat import backfill_employee_users
        Employee.objects.create(
            first_name="U", last_name="Only", email="uonly@example.com")
        User.objects.create(username="uonly@example.com")  # blank email
        matched, _ = backfill_employee_users()
        row = Employee.objects.get(email="uonly@example.com")
        print(f"PROBE:backfill-username-only:matched={matched}:"
              f"linked={row.user is not None}")
        self.assertIsNone(row.user)
