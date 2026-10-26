from django.urls import path
from accounts.views import password_login, account_update

from . import views

urlpatterns = [
    path("auth/account/", account_update, name="account_update"),
    path("health/", views.health, name="health"),
    path("auth/session/", views.session, name="auth_session"),
    path("auth/login/", password_login, name="auth_login"),
    path("auth/logout/", views.logout_view, name="auth_logout"),
]
