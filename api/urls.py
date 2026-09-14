from django.urls import path, include

urlpatterns = [
    # If you want api/ to share the same views as core, you can include core's URLs:
    path('', include('core.urls')),
]