"""
URL configuration for fuel_optimizer project.
"""

from django.contrib import admin
from django.urls import path, include
from routes.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("routes.urls")),
]
