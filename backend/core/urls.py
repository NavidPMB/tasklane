from django.urls import path
from accounts.views import password_login

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/session/", views.session, name="auth_session"),
    path("auth/login/", password_login, name="auth_login"),
    path("auth/logout/", views.logout_view, name="auth_logout"),
]
