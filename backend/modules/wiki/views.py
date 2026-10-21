from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Article


def article_metadata(article):
    return {
        "id": article.pk,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "visibility": article.visibility,
        "updatedAt": article.updated_at.isoformat(),
    }


@never_cache
@require_GET
def article_list(request):
    # Zuerst Berechtigungen anwenden; auch Suche und Zähler dürfen nichts verraten.
    articles = Article.objects.visible_to(request.user)
    query = request.GET.get("q", "").strip()[:200]
    visibility = request.GET.get("visibility", "")
    if visibility and visibility not in Article.Visibility.values:
        return JsonResponse({"error": "Ungültige Sichtbarkeit."}, status=400)
    if query:
        articles = articles.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(body__icontains=query))
    if visibility:
        articles = articles.filter(visibility=visibility)
    return JsonResponse({"articles": [article_metadata(article) for article in articles]})


@never_cache
@require_GET
def article_detail(request, slug):
    article = Article.objects.visible_to(request.user).filter(slug=slug).first()
    if article is None:
        # Identische Antwort für fehlende und nicht zugängliche Artikel.
        return JsonResponse({"error": "Artikel nicht gefunden."}, status=404)
    body = article.body.replace("{{GOOGLE_CALLBACK_URL}}", f"{settings.PUBLIC_URL}/accounts/google/login/callback/")
    body = body.replace("{{PUBLIC_URL}}", settings.PUBLIC_URL)
    return JsonResponse({**article_metadata(article), "body": body})
