from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import Employee, Notification
from core.notifications import notify_employee
from core.views_notifications import NotificationListView, NotificationMarkReadView


class NotificationWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="inbox-owner", is_staff=True)
        self.other_user = user_model.objects.create_user(username="inbox-other")
        self.employee = Employee.objects.create(user=self.user, first_name="Inbox", last_name="Owner", email="inbox-owner@example.com")
        self.other = Employee.objects.create(user=self.other_user, first_name="Inbox", last_name="Other", email="inbox-other@example.com")
        self.factory = APIRequestFactory()

    def request(self, view, method="get", pk=None):
        request = getattr(self.factory, method)("/api/notifications/")
        force_authenticate(request, self.user)
        return view.as_view()(request, **({"pk": pk} if pk else {}))

    def test_deduplication_and_rollback(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                notify_employee(self.employee, "Updated", "leave", event_key="test:rollback")
                raise RuntimeError()
        self.assertFalse(Notification.objects.filter(event_key="test:rollback").exists())
        first = notify_employee(self.employee, "Updated", "leave", event_key="test:once")
        second = notify_employee(self.employee, "Updated", "leave", event_key="test:once")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.filter(event_key="test:once").count(), 1)

    def test_staff_inbox_is_private_muted_and_read_is_idempotent(self):
        own = notify_employee(self.employee, "Own", "leave")
        notify_employee(self.employee, "Muted", "payroll")
        foreign = notify_employee(self.other, "Private", "leave")
        self.user.setting.muted_kinds = ["payroll"]
        self.user.setting.save(update_fields=["muted_kinds"])
        response = self.request(NotificationListView)
        self.assertEqual([row["id"] for row in response.data["results"]], [str(own.pk)])
        self.assertEqual(self.request(NotificationMarkReadView, "patch", foreign.pk).status_code, 404)
        for _ in range(2):
            response = self.request(NotificationMarkReadView, "patch", own.pk)
            self.assertTrue(response.data["is_read"])
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        self.assertEqual(self.request(NotificationMarkReadView, "patch", own.pk).status_code, 404)
