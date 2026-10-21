from django.urls import path
from . import views

urlpatterns = [
    path('workspaces/', views.workspaces),
    path('projects/', views.projects),
    path('projects/<int:project_id>/', views.project),
    path('actions/', views.actions),
    path('time/entries/', views.time_entries),
    path('time/report/', views.time_report),
    path('time/export/', views.time_export),
]
