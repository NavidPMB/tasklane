from django.conf import settings
from django.db import models


class ArticleQuerySet(models.QuerySet):
    def visible_to(self, user):
        visibility = [Article.Visibility.PUBLIC]
        if user.is_authenticated and user.is_active:
            visibility.append(Article.Visibility.REGISTERED)
            if user.is_superuser:
                visibility.append(Article.Visibility.INTERNAL)
        return self.filter(is_published=True, visibility__in=visibility)


class Article(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public", "Öffentlich"
        REGISTERED = "registered", "Angemeldete Benutzer"
        INTERNAL = "internal", "Intern · nur Superuser"

    title = models.CharField("Titel", max_length=180)
    slug = models.SlugField("URL-Schlüssel", unique=True, max_length=180)
    summary = models.CharField("Kurzbeschreibung", max_length=300, blank=True)
    body = models.TextField("Inhalt (Markdown)", help_text="Keine Secrets oder Zugangsdaten eintragen. {{PUBLIC_URL}} und {{GOOGLE_CALLBACK_URL}} zeigen die aktuellen Projekt-URLs an.")
    visibility = models.CharField("Sichtbarkeit", max_length=20, choices=Visibility.choices, default=Visibility.INTERNAL)
    is_published = models.BooleanField("Veröffentlicht", default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Zuletzt bearbeitet von", null=True, blank=True, on_delete=models.SET_NULL, editable=False)
    created_at = models.DateTimeField("Erstellt am", auto_now_add=True)
    updated_at = models.DateTimeField("Aktualisiert am", auto_now=True)
    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "Wiki-Artikel"
        verbose_name_plural = "Wiki-Artikel"
        ordering = ["title", "id"]
        indexes = [models.Index(fields=["is_published", "visibility"], name="wiki_published_visibility")]

    def __str__(self):
        return self.title
