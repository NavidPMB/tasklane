from django.urls import path
from . import views

urlpatterns = [
    path('access-tokens/', views.access_tokens),
    path('projects/<int:project_id>/tickets/<int:ticket_id>/attachments/', views.attachment_upload),
    path('projects/<int:project_id>/attachments/<uuid:attachment_id>/content/', views.attachment_download),
    path('workspaces/', views.workspaces),
    path('projects/', views.projects),
    path('projects/<int:project_id>/', views.project),
    path('actions/', views.actions),
    path('time/entries/', views.time_entries),
    path('time/report/', views.time_report),
    path('time/export/', views.time_export),
]
