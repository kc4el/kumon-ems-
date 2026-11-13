from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import (Attendance, AttendanceCorrection, Employee, Notification,
                         OvertimeSlip, PayEstimatePolicy, ShiftRoster, ShiftSwap)
from core.views_staff_requests import (AttendanceCorrectionDetailView,
    AttendanceCorrectionListCreateView, AvailableShiftRosterView, OvertimeSlipDetailView,
    OvertimeSlipListCreateView, ShiftRosterListCreateView, ShiftSwapDetailView,
    ShiftSwapListCreateView)
from core.views_staff_requests import OvertimeRecalculateView
from core.views_actions import ShiftSwapDecideView, AttendanceCorrectionApproveView


class StaffRequestsTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.staff = User.objects.create_user("hr", is_staff=True)
        self.user = User.objects.create_user("one")
        self.other_user = User.objects.create_user("two")
        self.employee = Employee.objects.create(first_name="One", last_name="Person", email="one@test.test", user=self.user)
        self.other = Employee.objects.create(first_name="Two", last_name="Person", email="two@test.test", user=self.other_user)
        self.day = date(2026, 6, 1)
        self.a = ShiftRoster.objects.create(employee=self.employee, work_date=self.day, start_time=time(8), end_time=time(16), break_mins=60)
        self.b = ShiftRoster.objects.create(employee=self.other, work_date=self.day, start_time=time(16), end_time=time(23))
        self.att = Attendance.objects.create(employee=self.employee, date=self.day, clock_in=timezone.make_aware(datetime(2026, 6, 1, 8)), clock_out=timezone.make_aware(datetime(2026, 6, 1, 18)))

    def call(self, view, method, user, data=None, pk=None, query=""):
        req = getattr(self.factory, method)("/test/" + query, data or {}, format="json")
        force_authenticate(req, user)
        kwargs = {"pk": pk} if pk else {}
        return view.as_view()(req, **kwargs)

    def test_roster_scoping_and_available_minimal_fields(self):
        response = self.call(ShiftRosterListCreateView, "get", self.user, query="?start_date=2026-06-01&end_date=2026-06-01")
        self.assertEqual([r["id"] for r in response.data["results"]], [str(self.a.pk)])
        response = self.call(AvailableShiftRosterView, "get", self.user, query="?work_date=2026-06-01")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["employee_name"], "Two Person")
        self.assertEqual(set(response.data[0]), {"id", "employee_name", "work_date", "start_time", "end_time", "shift_type"})
        self.assertEqual(self.call(ShiftRosterListCreateView, "post", self.user, {"employee": str(self.employee.pk), "work_date": "2026-06-02", "start_time": "08:00", "end_time": "16:00"}).status_code, 403)

    def test_swap_decision_and_repeat_action(self):
        response = self.call(ShiftSwapListCreateView, "post", self.user, {"requester_roster": str(self.a.pk), "target_roster": str(self.b.pk), "reason": "Appointment"})
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertEqual(self.call(ShiftSwapDetailView, "patch", self.user, {"status": "Approved"}, pk).status_code, 403)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", self.other_user, {"decision": "Approved"}, pk).status_code, 200)
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual(self.a.employee_id, self.other.pk)
        self.assertEqual(self.b.employee_id, self.employee.pk)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", self.staff, {"decision": "Approved"}, pk).status_code, 409)
        self.assertEqual(Notification.objects.filter(text__contains="swap approved").count(), 2)

    def test_swap_overlap_rolls_back(self):
        swap = ShiftSwap.objects.create(requester_roster=self.a, target_roster=self.b, requester_employee=self.employee, target_employee=self.other)
        ShiftRoster.objects.create(employee=self.other, work_date=self.day, start_time=time(9), end_time=time(10))
        response = self.call(ShiftSwapDetailView, "patch", self.other_user, {"status": "Approved"}, swap.pk)
        self.assertEqual(response.status_code, 409)
        self.a.refresh_from_db(); swap.refresh_from_db()
        self.assertEqual(self.a.employee_id, self.employee.pk)
        self.assertEqual(swap.status, "Pending")

    def test_correction_hr_decision_applies_once(self):
        data = {"attendance": str(self.att.pk), "proposed_clock_out": "2026-06-01T19:00:00Z", "reason": "Forgot"}
        self.assertEqual(self.call(AttendanceCorrectionListCreateView, "post", self.user, {**data, "status": "Approved"}).status_code, 400)
        response = self.call(AttendanceCorrectionListCreateView, "post", self.user, data)
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertEqual(self.call(AttendanceCorrectionDetailView, "put", self.user, {"status": "Approved"}, pk).status_code, 403)
        self.assertEqual(self.call(AttendanceCorrectionApproveView, "post", self.staff, pk=pk).status_code, 200)
        self.att.refresh_from_db()
        self.assertEqual(self.att.clock_out, datetime.fromisoformat("2026-06-01T19:00:00+00:00"))
        self.assertEqual(self.call(AttendanceCorrectionDetailView, "patch", self.staff, {"status": "Rejected"}, pk).status_code, 409)
        self.assertEqual(Notification.objects.filter(text__contains="correction approved").count(), 1)

    def test_overtime_effective_policy_and_schedule_break(self):
        data = {"attendance": str(self.att.pk)}
        response = self.call(OvertimeSlipListCreateView, "post", self.user, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Configure", str(response.data))
        PayEstimatePolicy.objects.create(effective_date=self.day-timedelta(days=1), overtime_threshold_hours=Decimal("7"), overtime_multiplier=Decimal("1.50"))
        PayEstimatePolicy.objects.create(effective_date=self.day+timedelta(days=1), overtime_threshold_hours=Decimal("2"), overtime_multiplier=Decimal("2"))
        response = self.call(OvertimeSlipListCreateView, "post", self.user, data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["hours"], "2.00")
        self.assertEqual(response.data["multiplier"], "1.50")
        pk = response.data["id"]
        self.assertEqual(self.call(OvertimeSlipDetailView, "patch", self.staff, {"status": "Approved", "hours": "99"}, pk).status_code, 400)
        self.assertEqual(self.call(OvertimeSlipDetailView, "patch", self.staff, {"status": "Approved"}, pk).status_code, 200)
        self.assertEqual(self.call(OvertimeSlipDetailView, "patch", self.staff, {"status": "Approved"}, pk).status_code, 409)

    def test_inactive_profile_and_forged_owner_rejected(self):
        other_att = Attendance.objects.create(employee=self.other, date=self.day)
        response = self.call(AttendanceCorrectionListCreateView, "post", self.user, {"attendance": str(other_att.pk), "proposed_clock_in": "2026-06-01T08:00:00Z", "reason": "test"})
        self.assertEqual(response.status_code, 403)
        self.employee.is_active = False
        self.employee.save()
        self.assertEqual(self.call(ShiftRosterListCreateView, "get", self.user).status_code, 403)

    def test_changed_overtime_requires_recalculation_and_review(self):
        PayEstimatePolicy.objects.create(effective_date=self.day, overtime_threshold_hours=Decimal("7"), overtime_multiplier=Decimal("1.50"))
        created = self.call(OvertimeSlipListCreateView, "post", self.user, {"attendance": str(self.att.pk)})
        self.assertEqual(created.status_code, 201)
        pk = created.data["id"]
        self.att.clock_out -= timedelta(hours=1)
        self.att.save(update_fields=["clock_out"])
        self.assertEqual(self.call(OvertimeSlipDetailView, "patch", self.staff, {"status":"Approved"}, pk).status_code, 409)
        self.assertEqual(self.call(OvertimeRecalculateView, "post", self.user, pk=pk).status_code, 403)
        refreshed = self.call(OvertimeRecalculateView, "post", self.staff, pk=pk)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.data["status"], "Pending")
        self.assertEqual(refreshed.data["hours"], "1.00")
        self.assertEqual(self.call(OvertimeSlipDetailView, "patch", self.staff, {"status":"Approved"}, pk).status_code, 200)

    def test_swap_history_remains_visible_only_to_original_participants(self):
        swap = ShiftSwap.objects.create(requester_roster=self.a, target_roster=self.b, requester_employee=self.employee, target_employee=self.other, reason="Private reason")
        third_user = User.objects.create_user("third")
        third = Employee.objects.create(first_name="Third", last_name="Person", email="third@test.test", user=third_user)
        self.b.employee = third
        self.b.save(update_fields=["employee"])
        self.assertEqual(self.call(ShiftSwapDetailView, "get", third_user, pk=swap.pk).status_code, 404)
        self.assertEqual(self.call(ShiftSwapDetailView, "get", self.other_user, pk=swap.pk).status_code, 200)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", third_user, {"decision": "Approved"}, swap.pk).status_code, 403)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", self.other_user, {"decision": "Approved"}, swap.pk).status_code, 409)
        swap.refresh_from_db()
        self.assertEqual(swap.status, "Pending")

    def test_legacy_swap_with_unknown_parties_is_hr_only(self):
        swap = ShiftSwap.objects.create(requester_roster=self.a, target_roster=self.b, reason="Private")
        self.assertEqual(self.call(ShiftSwapDetailView, "get", self.user, pk=swap.pk).status_code, 404)
        self.assertEqual(self.call(ShiftSwapDetailView, "get", self.staff, pk=swap.pk).status_code, 200)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", self.other_user, {"decision": "Approved"}, swap.pk).status_code, 403)
        self.assertEqual(self.call(ShiftSwapDecideView, "post", self.staff, {"decision": "Approved"}, swap.pk).status_code, 409)
