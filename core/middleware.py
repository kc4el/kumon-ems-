from django.http import JsonResponse
from django.shortcuts import redirect

from .models import Employee


class OnboardingAccessMiddleware:
    """Keep not-yet-linked employees inside the onboarding flow."""

    allowed_paths = {
        "/onboarding/",
        "/api/auth/google/link/",
        "/api/auth/google/link",
        "/api/auth/google/callback/",
        "/api/auth/google/callback",
        "/api/session-logout/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            employee = Employee.objects.filter(user=user).only(
                "status", "force_password_change"
            ).first()
            restricted = bool(
                employee
                and (
                    employee.status == Employee.OnboardingStatus.PENDING_ONBOARDING
                    or employee.force_password_change
                )
            )
            if (
                restricted
                and request.path not in self.allowed_paths
                and not request.path.startswith("/static/")
            ):
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Complete account onboarding before using this service."},
                        status=403,
                    )
                return redirect("/onboarding/")
        return self.get_response(request)
