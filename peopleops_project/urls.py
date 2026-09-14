from django.contrib import admin
from django.urls import path, include
from core.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('core/', include('core.urls')),
    path('api/', include('api.urls')),
]