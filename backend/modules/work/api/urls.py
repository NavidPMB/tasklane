from django.urls import path
from . import views
urlpatterns = [
    path('openapi.json', views.openapi),
    path('actions', views.capabilities),
    path('actions/<str:action>', views.action),
    path('projects', views.projects),
    path('workspaces', views.workspaces),
    path('projects/<int:project_id>', views.project),
    path('projects/<int:project_id>/tickets/<int:ticket_id>', views.ticket),
    path('projects/<int:project_id>/attachments/<uuid:attachment_id>/content', views.attachment_download),
]
