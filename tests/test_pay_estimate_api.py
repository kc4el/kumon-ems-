from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Attendance, Employee, EmployeeAuditLog, PayEstimatePolicy, ShiftRoster

LOCAL = timezone(timedelta(hours=8))


class PayEstimateAPITests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.staff = users.create_user(username="estimate-hr", is_staff=True)
        self.user = users.create_user(username="estimate-employee")
        self.employee = Employee.objects.create(user=self.user, first_name="Estimate", last_name="Employee", email="estimate@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.day = date(2026, 3, 2)
        self.policy = {"effective_date": "2026-01-01", "overtime_threshold_hours": "8.0000", "overtime_multiplier": "1.5000", "paid_leave_types": ["Vacation"]}
        response = self.client.post("/api/pay-estimate-policies/", self.policy, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        ShiftRoster.objects.create(employee=self.employee, work_date=self.day, start_time=time(9), end_time=time(18), break_mins=0)
        self.attendance = Attendance.objects.create(employee=self.employee, date=self.day,
            clock_in=datetime(2026, 3, 2, 9, tzinfo=LOCAL), clock_out=datetime(2026, 3, 2, 18, tzinfo=LOCAL))

    def create_estimate(self):
        result = self.client.post("/api/pay-estimates/", {"employee": str(self.employee.pk), "period_start": "2026-03-02", "period_end": "2026-03-02", "hourly_rate": "100.00", "deductions": "20.00"}, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        return result.data

    def test_employee_and_anonymous_cannot_access_any_estimate_endpoint(self):
        estimate = self.create_estimate()
        pk = estimate["id"]
        adjustment = estimate["revision"]["adjustments"][0]["id"]
        actions = [("get", "/api/pay-estimate-policies/"), ("post", "/api/pay-estimate-policies/"),
                   ("get", "/api/pay-estimates/"), ("post", "/api/pay-estimates/"),
                   ("get", f"/api/pay-estimates/{pk}/"), ("patch", f"/api/pay-estimates/{pk}/"),
                   ("post", f"/api/pay-estimates/{pk}/recalculate/"),
                   ("get", f"/api/pay-estimates/{pk}/revisions/1/"),
                   ("get", f"/api/pay-estimates/{pk}/export/?format=csv"),
                   ("post", f"/api/pay-estimate-adjustments/{adjustment}/decision/")]
        for actor in (self.user, None):
            self.client.force_authenticate(actor)
            for method, url in actions:
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertIn(response.status_code, (401, 403), (actor, url, response.status_code))
        inactive_hr = get_user_model().objects.create_user(username="inactive-profile-hr", is_staff=True)
        Employee.objects.create(user=inactive_hr, first_name="Former", last_name="HR", email="formerhr@example.com", is_active=False)
        self.client.force_authenticate(inactive_hr)
        self.assertEqual(self.client.get("/api/pay-estimates/").status_code, 403)

    def test_approval_is_idempotent_and_only_approved_adjustments_count(self):
        data = self.create_estimate()
        revision = data["revision"]
        self.assertTrue(revision["is_complete"])
        self.assertEqual(Decimal(revision["base_amount"]), Decimal("900"))
        self.assertEqual(Decimal(revision["approved_estimate"]), Decimal("880"))
        item = revision["adjustments"][0]
        self.assertEqual(Decimal(item["amount"]), Decimal("50"))
        url = f"/api/pay-estimate-adjustments/{item['id']}/decision/"
        before = EmployeeAuditLog.objects.count()
        self.assertEqual(self.client.post(url, {"status": "Approved"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {"status": "Approved"}, format="json").status_code, 200)
        self.assertEqual(EmployeeAuditLog.objects.count(), before + 1)
        self.assertEqual(self.client.post(url, {"status": "Rejected", "reason": "changed"}, format="json").status_code, 409)
        latest = self.client.get(f"/api/pay-estimates/{data['id']}/").data["revision"]
        self.assertEqual(Decimal(latest["approved_estimate"]), Decimal("930"))
        export = self.client.get(f"/api/pay-estimates/{data['id']}/export/?format=csv")
        self.assertEqual(export.status_code, 200)
        self.assertIn("PAY ESTIMATE", export.content.decode())

    def test_stale_history_and_incomplete_revisions_cannot_be_approved(self):
        data = self.create_estimate()
        pk = data["id"]
        item = data["revision"]["adjustments"][0]["id"]
        self.attendance.clock_out = datetime(2026, 3, 2, 17, 30, tzinfo=LOCAL)
        self.attendance.save()
        response = self.client.get(f"/api/pay-estimates/{pk}/")
        self.assertTrue(response.data["revision"]["is_stale"])
        self.assertIsNone(response.data["revision"]["approved_estimate"])
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{item}/decision/", {"status": "Approved"}, format="json").status_code, 409)
        revised = self.client.post(f"/api/pay-estimates/{pk}/recalculate/").data
        self.assertEqual(revised["current_revision"], 2)
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{item}/decision/", {"status": "Approved"}, format="json").status_code, 409)
        # Add another open attendance to make the revision incomplete without losing the overtime candidate.
        Attendance.objects.create(employee=self.employee, date=date(2026, 3, 3), clock_in=datetime(2026, 3, 3, 9, tzinfo=LOCAL))
        self.client.patch(f"/api/pay-estimates/{pk}/", {"period_end": "2026-03-03"}, format="json")
        incomplete = self.client.post(f"/api/pay-estimates/{pk}/recalculate/").data["revision"]
        self.assertFalse(incomplete["is_complete"])
        new_item = incomplete["adjustments"][0]["id"]
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{new_item}/decision/", {"status": "Approved"}, format="json").status_code, 409)
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{new_item}/decision/", {"status": "Rejected"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{new_item}/decision/", {"status": "Rejected", "reason": "Review needed"}, format="json").status_code, 200)
        historical = self.client.get(f"/api/pay-estimates/{pk}/revisions/1/").data["revision"]
        self.assertTrue(historical["is_stale"])
        self.assertIsNone(historical["approved_estimate"])

    def test_validation_and_immutable_policy(self):
        self.assertEqual(self.client.post("/api/pay-estimate-policies/", self.policy, format="json").status_code, 201)
        invalid = dict(self.policy, effective_date="2026-02-01", overtime_multiplier=None)
        self.assertEqual(self.client.post("/api/pay-estimate-policies/", invalid, format="json").status_code, 400)
        self.assertIn(self.client.patch("/api/pay-estimate-policies/", {}, format="json").status_code, (404, 405))
        data = {"employee": str(self.employee.pk), "period_start": "2026-03-02", "period_end": "2026-03-02", "hourly_rate": "100.001", "deductions": "0.00"}
        self.assertEqual(self.client.post("/api/pay-estimates/", data, format="json").status_code, 400)
        data["hourly_rate"] = "-1.00"
        self.assertEqual(self.client.post("/api/pay-estimates/", data, format="json").status_code, 400)
        self.assertEqual(PayEstimatePolicy.objects.count(), 2)

    def test_revisions_preserve_decisions_and_historical_inputs(self):
        data = self.create_estimate()
        pk = data["id"]
        item = data["revision"]["adjustments"][0]["id"]
        url = f"/api/pay-estimate-adjustments/{item}/decision/"
        self.assertEqual(self.client.post(url, {"status": "Approved"}, format="json").status_code, 200)
        changed = self.client.patch(f"/api/pay-estimates/{pk}/", {"hourly_rate": "125.00"}, format="json").data
        self.assertTrue(changed["revision"]["is_stale"])
        revised = self.client.post(f"/api/pay-estimates/{pk}/recalculate/").data
        self.assertEqual(revised["revision"]["adjustments"][0]["status"], "Pending")
        previous = self.client.get(f"/api/pay-estimates/{pk}/revisions/1/").data
        self.assertEqual(previous["hourly_rate"], "100.00")
        self.assertEqual(previous["current_inputs"]["hourly_rate"], "125.00")
        self.assertEqual(previous["revision"]["adjustments"][0]["status"], "Approved")
        self.assertEqual(Decimal(previous["revision"]["snapshot_estimate"]), Decimal("930.00"))
        self.assertEqual(self.client.post(url, {"status": "Approved"}, format="json").status_code, 409)

    def test_estimate_audit_events_are_not_visible_in_employee_feeds(self):
        data = self.create_estimate()
        item = data["revision"]["adjustments"][0]["id"]
        self.assertEqual(self.client.post(f"/api/pay-estimate-adjustments/{item}/decision/", {"status": "Approved"}, format="json").status_code, 200)
        logs = EmployeeAuditLog.objects.filter(action__startswith="Pay estimate")
        self.assertEqual(logs.count(), 2)
        self.assertFalse(logs.exclude(employee=None).exists())
        self.client.force_authenticate(self.user)
        for url in ("/api/audit-logs/", "/api/logs/"):
            response = self.client.get(url)
            self.assertIn(response.status_code, (200, 403))
            self.assertNotIn("Pay estimate", response.content.decode())
            self.assertNotIn(data["id"], response.content.decode())
