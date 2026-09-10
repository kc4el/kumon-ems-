from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic import RedirectView

from core.views import dashboard_view, login_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard_view, name="dashboard"),
    path("login/", login_view, name="login"),
    path("signup/", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("auth/", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("core/", include("core.urls")),
    path("api/", include("api.urls")),
]

from django.contrib.staticfiles.views import serve
from django.urls import re_path

urlpatterns += [
    re_path(r"^static/(?P<path>.*)$", serve, {"insecure": True}),
]
