from django.contrib import admin
from django.utils.html import format_html

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "visibility", "is_published", "updated_at", "updated_by")
    list_filter = ("visibility", "is_published")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("frontend_link", "updated_by", "created_at", "updated_at")
    fieldsets = (
        ("Artikel", {"fields": ("title", "slug", "summary", "body")}),
        ("Zugriff & Veröffentlichung", {"fields": ("visibility", "is_published", "frontend_link")}),
        ("Bearbeitung", {"fields": ("updated_by", "created_at", "updated_at")}),
    )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Im Wiki öffnen")
    def frontend_link(self, obj):
        if not obj or not obj.pk:
            return "Nach dem Speichern und Veröffentlichen im Wiki verfügbar."
        return format_html('<a href="/wiki/{}">Artikel öffnen</a> · Entwürfe sind nur hier im Admin sichtbar.', obj.slug)
