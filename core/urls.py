from django.urls import path
from .views import dashboard_view, login_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('signup/', login_view, name='signup'),
    path('auth/', login_view, name='auth'),
]