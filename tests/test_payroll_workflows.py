from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Employee, Notification, PayrollItem, PayrollRun


class PayrollWorkflowTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.staff = users.create_user(username="payroll-staff", is_staff=True)
        self.user = users.create_user(username="payroll-employee")
        self.other_user = users.create_user(username="payroll-other")
        self.employee = Employee.objects.create(user=self.user, first_name="Pay", last_name="One", email="pay-one@example.com")
        self.other = Employee.objects.create(user=self.other_user, first_name="Pay", last_name="Two", email="pay-two@example.com")
        self.run = PayrollRun.objects.create(pay_period_start=date(2026, 1, 1), pay_period_end=date(2026, 1, 31))
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def payload(self, **overrides):
        data = {"payroll_run": str(self.run.pk), "employee": str(self.employee.pk), "base_pay": "15000.00", "deductions": "1500.00"}
        data.update(overrides)
        return data

    def create_item(self):
        response = self.client.post("/api/payroll-items/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_validation_and_calculation(self):
        for overrides in ({"base_pay": "-1"}, {"deductions": "-1"}, {"deductions": "16000"}, {"base_pay": "1.001"}):
            self.assertEqual(self.client.post("/api/payroll-items/", self.payload(**overrides), format="json").status_code, 400)
        self.assertEqual(self.create_item()["net_pay"], "13500.00")
        self.assertEqual(self.client.post("/api/payroll-items/", self.payload(), format="json").status_code, 409)
        self.assertEqual(self.client.post("/api/payroll-runs/", {"pay_period_start": "2026-02-01", "pay_period_end": "2026-01-01"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/payroll-runs/{self.run.pk}/", {"is_processed": True}, format="json").status_code, 400)

    def test_permissions_and_finalized_visibility(self):
        row = self.create_item()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/payroll-runs/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/payroll-items/{row['id']}/").status_code, 404)
        self.assertEqual(self.client.post("/api/payroll-items/", self.payload(), format="json").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/payroll-items/{row['id']}/", {"base_pay": "20"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/payroll-runs/{self.run.pk}/finalize/").status_code, 403)
        self.run.is_processed = True
        self.run.save(update_fields=["is_processed"])
        self.assertEqual(self.client.get(f"/api/payroll-items/{row['id']}/").status_code, 200)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(f"/api/payroll-items/{row['id']}/").status_code, 404)

    @patch("core.notifications.notify_employee")
    def test_finalize_recomputes_notifies_once_and_locks_every_write(self, notify):
        self.assertEqual(self.client.post(f"/api/payroll-runs/{self.run.pk}/finalize/").status_code, 400)
        row = self.create_item()
        PayrollItem.objects.filter(pk=row["id"]).update(net_pay=Decimal("1.00"))
        self.assertEqual(self.client.post(f"/api/payroll-runs/{self.run.pk}/finalize/").status_code, 200)
        self.assertEqual(PayrollItem.objects.get(pk=row["id"]).net_pay, Decimal("13500.00"))
        self.assertEqual(self.client.post(f"/api/payroll-runs/{self.run.pk}/finalize/").status_code, 200)
        self.assertEqual(notify.call_count, 1)
        self.assertEqual(notify.call_args.kwargs["event_key"], f"payroll:{self.run.pk}:{row['id']}:finalized")
        self.assertEqual(self.client.patch(f"/api/payroll-items/{row['id']}/", {"base_pay": "99.00"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/payroll-items/{row['id']}/").status_code, 400)
        self.assertEqual(self.client.post("/api/payroll-items/", self.payload(employee=str(self.other.pk)), format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/payroll-runs/{self.run.pk}/", {"pay_period_end": "2026-02-01"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/payroll-runs/{self.run.pk}/").status_code, 400)

    def test_move_between_open_and_finalized_runs_is_rejected(self):
        row = self.create_item()
        closed = PayrollRun.objects.create(pay_period_start=date(2026, 2, 1), pay_period_end=date(2026, 2, 28), is_processed=True)
        self.assertEqual(self.client.patch(f"/api/payroll-items/{row['id']}/", {"payroll_run": str(closed.pk)}, format="json").status_code, 400)
        PayrollItem.objects.filter(pk=row["id"]).update(payroll_run=closed)
        self.assertEqual(self.client.patch(f"/api/payroll-items/{row['id']}/", {"payroll_run": str(self.run.pk)}, format="json").status_code, 400)

    def test_notifications_only_after_finalize_and_never_duplicated(self):
        row = self.create_item()
        self.assertFalse(Notification.objects.filter(employee=self.employee, kind="payroll").exists())
        url = f"/api/payroll-runs/{self.run.pk}/finalize/"
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        notices = Notification.objects.filter(employee=self.employee, kind="payroll")
        self.assertEqual(notices.count(), 1)
        self.assertEqual(str(notices.get().target_id), row["id"])
