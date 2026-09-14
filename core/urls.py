from django.urls import path

from .views import attendance_checkin_view, dashboard_view, login_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("attendance-checkin/", attendance_checkin_view, name="attendance-checkin"),
    path("login/", login_view, name="login"),
    path("signup/", login_view, name="signup"),
    path("auth/", login_view, name="auth"),
]
