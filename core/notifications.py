"""Transactional in-app notification creation."""

from .models import Notification


def notify_employee(employee, text, kind, target_type="", target_id=None, event_key=None):
    defaults = {
        "employee": employee, "text": text, "kind": kind,
        "target_type": target_type, "target_id": target_id,
    }
    if event_key is None:
        return Notification.objects.create(**defaults)
    notification, _ = Notification.objects.get_or_create(event_key=event_key, defaults=defaults)
    return notification
