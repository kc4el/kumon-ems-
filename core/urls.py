from django.urls import path

from .views import attendance_checkin_view, dashboard_view, employee_portal_view, hr_dashboard_view, hr_login_view, login_view
from .views_onboarding import hr_onboarding_view, onboarding_login_view, onboarding_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("attendance-checkin/", attendance_checkin_view, name="attendance-checkin"),
    path("login/", login_view, name="login"),
    path("hr/login/", hr_login_view, name="hr-login"),
    path("hr/", hr_dashboard_view, name="hr-dashboard"),
    path("hr/onboarding/", hr_onboarding_view, name="hr-onboarding"),
    path("employee/", employee_portal_view, name="employee-portal"),
    path("onboarding/login/", onboarding_login_view, name="onboarding-login"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("signup/", login_view, name="signup"),
    path("auth/", login_view, name="auth"),
]
