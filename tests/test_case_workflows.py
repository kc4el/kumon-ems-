from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import Complaint, Employee, EmployeeAuditLog, ExpenseClaim, Grievance, Notification
from core.views_workflows import (
    ClaimDecisionView, ComplaintDetailView, ComplaintEscalateView,
    ComplaintListCreateView, ExpenseClaimDetailView, ExpenseClaimListCreateView,
    GrievanceDetailView,
)


class CaseWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner")
        self.other = User.objects.create_user("other")
        self.hr = User.objects.create_user("hr", is_staff=True)
        self.employee = Employee.objects.create(user=self.owner, first_name="Owner", last_name="A", email="a@example.com")
        self.other_employee = Employee.objects.create(user=self.other, first_name="Other", last_name="B", email="b@example.com")
        self.factory = APIRequestFactory()

    def call(self, view, method, user, data=None, pk=None):
        request = getattr(self.factory, method)("/", data or {}, format="json")
        force_authenticate(request, user=user)
        response = view.as_view()(request, **({"pk": pk} if pk else {}))
        response.render()
        return response

    def test_claim_owner_decision_and_idempotency(self):
        response = self.call(ExpenseClaimListCreateView, "post", self.owner,
                             {"employee": str(self.other_employee.pk), "title": "Taxi", "amount": "10.00"})
        self.assertEqual(response.status_code, 201, response.data)
        claim = ExpenseClaim.objects.get()
        self.assertEqual(claim.employee, self.employee)
        self.assertEqual(claim.status, "Pending")
        self.assertEqual(self.call(ExpenseClaimDetailView, "get", self.other, pk=claim.pk).status_code, 404)
        self.assertEqual(self.call(ClaimDecisionView, "post", self.owner, {"status": "Approved"}, claim.pk).status_code, 403)
        self.assertEqual(self.call(ClaimDecisionView, "post", self.hr, {"decision": "Approved"}, claim.pk).status_code, 200)
        self.assertEqual(self.call(ClaimDecisionView, "post", self.hr, {"status": "Approved"}, claim.pk).status_code, 200)
        self.assertEqual(self.call(ClaimDecisionView, "post", self.hr, {"status": "Rejected"}, claim.pk).status_code, 409)
        self.assertEqual(self.call(ExpenseClaimDetailView, "patch", self.owner, {"title": "Changed"}, claim.pk).status_code, 400)
        self.assertEqual(Notification.objects.filter(employee=self.employee, target_id=claim.pk).count(), 1)
        self.assertFalse(EmployeeAuditLog.objects.filter(action__contains="Taxi").exists())

    def test_complaint_private_notes_and_transitions(self):
        response = self.call(ComplaintListCreateView, "post", self.owner,
                             {"employee": str(self.other_employee.pk), "subject": "Case", "description": "Sensitive"})
        self.assertEqual(response.status_code, 201, response.data)
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.employee, self.employee)
        self.assertNotIn("internal_notes", response.data)
        self.assertEqual(self.call(ComplaintDetailView, "patch", self.owner, {"status": "In Review"}, complaint.pk).status_code, 403)
        self.assertEqual(self.call(ComplaintDetailView, "patch", self.hr, {"status": "Resolved", "resolution": "Done"}, complaint.pk).status_code, 400)
        self.assertEqual(self.call(ComplaintDetailView, "patch", self.hr, {"status": "In Review", "internal_notes": "private"}, complaint.pk).status_code, 200)
        self.assertEqual(self.call(ComplaintDetailView, "patch", self.hr, {"status": "Resolved"}, complaint.pk).status_code, 400)
        self.assertEqual(self.call(ComplaintDetailView, "patch", self.hr, {"status": "Resolved", "resolution": "Done"}, complaint.pk).status_code, 200)
        self.assertEqual(Notification.objects.filter(target_id=complaint.pk).count(), 2)
        owner_view = self.call(ComplaintDetailView, "get", self.owner, pk=complaint.pk)
        self.assertNotIn("internal_notes", owner_view.data)
        self.assertEqual(owner_view.data["resolution"], "Done")
        self.assertFalse(EmployeeAuditLog.objects.filter(action__contains="Sensitive").exists())

    def test_escalation_and_grievance_closure(self):
        complaint = Complaint.objects.create(employee=self.employee, subject="Case", description="Details")
        self.assertEqual(self.call(ComplaintEscalateView, "post", self.owner, pk=complaint.pk).status_code, 403)
        created = self.call(ComplaintEscalateView, "post", self.hr, pk=complaint.pk)
        repeat = self.call(ComplaintEscalateView, "post", self.hr, pk=complaint.pk)
        self.assertEqual((created.status_code, repeat.status_code), (201, 200))
        self.assertEqual(created.data["id"], repeat.data["id"])
        grievance = Grievance.objects.get()
        self.assertEqual(self.call(GrievanceDetailView, "patch", self.hr, {"status": "Rejected", "resolution": "Explained"}, grievance.pk).status_code, 200)
        self.assertEqual(Notification.objects.filter(target_id=grievance.pk).count(), 1)
        self.assertNotIn("internal_notes", self.call(GrievanceDetailView, "get", self.owner, pk=grievance.pk).data)
        self.assertEqual(self.call(GrievanceDetailView, "get", self.other, pk=grievance.pk).status_code, 404)

    def test_inactive_employee_blocked(self):
        self.employee.is_active = False
        self.employee.save()
        self.assertEqual(self.call(ExpenseClaimListCreateView, "get", self.owner).status_code, 403)
