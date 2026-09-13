from django.db.models import Q
from rest_framework.permissions import BasePermission


def owns_object(obj, user):
    """True when ``user`` is the owner behind ``obj``.

    Traverses the identity links each model family offers: a direct
    ``user`` (Employee), ``employee.user`` (attendance, leave, payroll,
    notification, roster, review, expense rows), ``attendance.employee``
    (corrections, overtime slips via their attendance), and either swap
    party's roster employee (shift swaps). Anything without a resolvable
    owner returns False — unlinked rows are staff-only.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    direct = getattr(obj, "user", None)
    if direct is not None and direct == user:
        return True
    employee = getattr(obj, "employee", None)
    if employee is not None and getattr(employee, "user", None) == user:
        return True
    attendance = getattr(obj, "attendance", None)
    att_employee = (
        getattr(attendance, "employee", None) if attendance is not None else None
    )
    if att_employee is not None and getattr(att_employee, "user", None) == user:
        return True
    for attr in ("requester_roster", "target_roster"):
        roster = getattr(obj, attr, None)
        roster_employee = (
            getattr(roster, "employee", None) if roster is not None else None
        )
        if (
            roster_employee is not None
            and getattr(roster_employee, "user", None) == user
        ):
            return True
    return False


class IsOwnerOrStaff(BasePermission):
    """Object permission: staff see everything, others only their own rows.

    Inactive non-staff are blocked at the permission gate (staff bypass).
    Inactive means either the Django user is inactive or the linked
    Employee profile is inactive.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return True
        if getattr(user, "is_staff", False):
            return True
        if not getattr(user, "is_active", True):
            return False
        from .models import Employee

        if Employee.objects.filter(user=user, is_active=False).exists():
            return False
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user and user.is_staff:
            return True
        return owns_object(obj, user)


class OwnerQuerysetMixin:
    """Filter list querysets to the request user's own rows (staff see all).

    Set ``owner_lookup`` to the ORM traversal from the row to its User
    (e.g. ``"employee__user"``), or ``"__swap_parties__"`` for shift
    swaps, which are visible to either party's employee.
    """

    owner_lookup = "employee__user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False) or user.is_staff:
            return qs
        return self._scope_to_owner(qs, user)

    def _scope_to_owner(self, qs, user):
        if self.owner_lookup == "__swap_parties__":
            return qs.filter(
                Q(requester_roster__employee__user=user)
                | Q(target_roster__employee__user=user)
            )
        return qs.filter(**{self.owner_lookup: user})
