from django.urls import path

from .views import overview, users

urlpatterns = [
    path("", overview, name="admin_overview"),
    path("users/", users, name="admin_users"),
]
