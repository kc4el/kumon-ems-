from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Employee, LeaveRequest
from core.views_docs import SalaryAdvance


class RequestIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="request-owner")
        self.other = User.objects.create_user(username="request-other")
        self.hr = User.objects.create_user(username="request-hr", is_staff=True)
        self.employee = Employee.objects.create(first_name="Owner", last_name="One", email="owner@test.example", user=self.user)
        self.other_employee = Employee.objects.create(first_name="Other", last_name="Two", email="other@test.example", user=self.other)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def leave(self, status="Pending"):
        return LeaveRequest.objects.create(employee=self.employee, leave_type="Vacation", start_date=date(2026, 12, 1), end_date=date(2026, 12, 2), status=status)

    def test_owner_cannot_reassign_or_modify_decided_leave(self):
        leave = self.leave()
        url = f"/api/leaves/{leave.pk}/"
        self.assertEqual(self.client.patch(url, {"employee": str(self.other_employee.pk)}, format="json").status_code, 400)
        self.assertEqual(self.client.put(url, {"employee": str(self.employee.pk), "leave_type": "Vacation", "start_date": "2026-12-01", "end_date": "2026-12-02", "reason": "Changed"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"reason": "Changed"}, format="json").status_code, 200)
        leave.status = "Approved"
        leave.save(update_fields=["status"])
        self.assertEqual(self.client.patch(url, {"reason": "Changed again"}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(url).status_code, 409)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.patch(url, {"reason": "Intrusion"}, format="json").status_code, 403)

    def test_leave_decisions_are_isolated_idempotent_and_bulk_atomic(self):
        pending = self.leave()
        approved = self.leave("Approved")
        self.client.force_authenticate(self.hr)
        detail = f"/api/leaves/{pending.pk}/"
        self.assertEqual(self.client.patch(detail, {"status": "Approved", "reason": "Changed"}, format="json").status_code, 400)
        response = self.client.post("/api/leaves/bulk-decide/", {"ids": [str(pending.pk), str(approved.pk)], "decision": "Rejected"}, format="json")
        self.assertEqual(response.status_code, 409)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "Pending")
        self.assertEqual(self.client.post(f"/api/leaves/{pending.pk}/approve/").status_code, 200)
        self.assertEqual(self.client.patch(detail, {"status": "Approved"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/leaves/{pending.pk}/reject/").status_code, 409)

    def test_advance_finality_and_decision_isolation(self):
        advance = SalaryAdvance.objects.create(employee=self.employee, amount="100.00")
        url = f"/api/advances/{advance.pk}/"
        self.assertEqual(self.client.patch(url, {"employee": str(self.other_employee.pk)}, format="json").status_code, 400)
        self.assertEqual(self.client.put(url, {"employee": str(self.employee.pk), "amount": "100.00", "purpose": "Rent", "repayment_terms": "Next Payroll"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"purpose": "Rent"}, format="json").status_code, 200)
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.patch(url, {"decision": "Approved", "amount": "999.00"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"decision": "Approved"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"decision": "Approved"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"decision": "Rejected"}, format="json").status_code, 409)
        self.assertEqual(self.client.patch(url, {"amount": "999.00"}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(url).status_code, 409)
        advance.refresh_from_db()
        self.assertEqual(str(advance.amount), "100.00")
