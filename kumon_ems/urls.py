from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.http import Http404
from urllib.parse import urlsplit
import re

from core.views import (
    dashboard_view,
    email_confirmation_view,
    employee_portal_view,
    hr_dashboard_view,
    hr_login_view,
    login_view,
)
from core.views_onboarding import hr_onboarding_view, onboarding_login_view, onboarding_view


def private_message_media(request, **kwargs):
    # Files must pass conversation authorization at the API download endpoint.
    raise Http404

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard_view, name="dashboard"),
    path("login/", login_view, name="login"),
    path(
        "auth/confirm/",
        email_confirmation_view,
        name="email-confirmation-page",
    ),
    path("hr/login/", hr_login_view, name="hr-login"),
    path("hr/", hr_dashboard_view, name="hr-dashboard"),
    path("hr/onboarding/", hr_onboarding_view, name="hr-onboarding"),
    path("employee/", employee_portal_view, name="employee-portal"),
    path("onboarding/login/", onboarding_login_view, name="onboarding-login"),
    path("new-staff/login/", onboarding_login_view, name="new-staff-login"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("signup/", RedirectView.as_view(url="/login/", permanent=False)),
    path("auth/", RedirectView.as_view(url="/login/", permanent=False)),
    path("core/", include("core.urls")),
    path("api/", include("api.urls")),
]

from django.contrib.staticfiles.views import serve
from django.urls import re_path

urlpatterns += [
    re_path(r"^" + re.escape(urlsplit(settings.MEDIA_URL).path.lstrip("/")) + r"message-attachments(?:/.*)?$", private_message_media),
    re_path(r"^static/(?P<path>.*)$", serve, {"insecure": True}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
