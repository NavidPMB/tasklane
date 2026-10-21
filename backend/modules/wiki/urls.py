from django.urls import path

from . import views

urlpatterns = [
    path("", views.article_list, name="wiki_list"),
    path("<slug:slug>/", views.article_detail, name="wiki_detail"),
]
