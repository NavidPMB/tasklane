from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import google_login

urlpatterns = [
    path("api/v1/", include("modules.work.api.urls")),
    path("django-admin/", admin.site.urls),
    path("accounts/login/", RedirectView.as_view(url=settings.LOGIN_URL)),
    path("accounts/google/login/", google_login, name="google_login_start"),
    path("accounts/", include("allauth.urls")),
    path("api/", include("core.urls")),
    path("api/cms/", include("modules.cms.urls")),
    path("api/dashboard/", include("modules.dashboard.urls")),
    path("api/admin/", include("modules.administration.urls")),
    path("api/wiki/", include("modules.wiki.urls")),
    path("api/work/", include("modules.work.urls")),
]
