import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { VisibilityBadge } from "@/components/wiki/visibility-badge";
import { backendFetch, getSession } from "@/lib/auth";
import { visibilityLabels, type Visibility, type WikiEntry } from "@/lib/wiki";

export const metadata: Metadata = { title: "Wiki" };

export default async function WikiPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; visibility?: string }>;
}) {
  const session = await getSession();
  const params = await searchParams;
  const query = (params.q || "").trim().slice(0, 200);
  const allowedVisibility: Visibility[] = ["public"];
  if (session.authenticated) allowedVisibility.push("registered");
  if (session.user?.isSuperuser) allowedVisibility.push("internal");
  const visibility = allowedVisibility.includes(params.visibility as Visibility)
    ? params.visibility || ""
    : "";
  const apiParams = new URLSearchParams({ q: query, visibility });
  const { articles } = await backendFetch<{ articles: WikiEntry[] }>(
    `/api/wiki/?${apiParams}`,
  );

  return (
    <main id="wiki-content" className="wiki-container">
      <div className="wiki-heading-row">
        <div className="page-heading">
          <p className="eyebrow">Wissensbereich</p>
          <h1>Ein Ort für Wissen.</h1>
          <p>
            Anleitungen, Antworten und Dokumentation für deinen Arbeitsbereich.
          </p>
        </div>
        {session.user?.isSuperuser && (
          <a href="/django-admin/wiki/article/" className="button button-small">
            Artikel verwalten <Icon name="arrow" width={16} height={16} />
          </a>
        )}
      </div>
      <form action="/wiki" method="get" className="wiki-search" role="search">
        <div className="wiki-search-input">
          <label htmlFor="wiki-query">Wiki durchsuchen</label>
          <input
            id="wiki-query"
            name="q"
            type="search"
            placeholder="Nach einer Anleitung suchen …"
            defaultValue={query}
            maxLength={200}
          />
        </div>
        <div className="wiki-filter">
          <label htmlFor="wiki-visibility">Sichtbarkeit</label>
          <select
            id="wiki-visibility"
            name="visibility"
            defaultValue={visibility}
          >
            <option value="">Alle verfügbaren Artikel</option>
            {allowedVisibility.map((value) => (
              <option key={value} value={value}>
                {visibilityLabels[value]}
              </option>
            ))}
          </select>
        </div>
        <button className="button" type="submit">
          Suchen <Icon name="arrow" width={16} height={16} />
        </button>
      </form>
      <div className="wiki-results-heading">
        <h2>{query ? "Suchergebnisse" : "Alle Artikel"}</h2>
        <span>{articles.length} Artikel</span>
        {(query || visibility) && (
          <Link href="/wiki" className="text-link">
            Filter zurücksetzen
          </Link>
        )}
      </div>
      {articles.length ? (
        <div className="wiki-articles">
          {articles.map((article) => (
            <Link
              href={`/wiki/${article.slug}`}
              className="wiki-article-card"
              key={article.id}
            >
              <div className="wiki-card-icon">
                <Icon name="book" width={23} height={23} />
              </div>
              <div className="wiki-card-copy">
                <VisibilityBadge visibility={article.visibility} />
                <h3>{article.title}</h3>
                {article.summary && <p>{article.summary}</p>}
              </div>
              <Icon name="arrow" className="wiki-card-arrow" />
            </Link>
          ))}
        </div>
      ) : (
        <section className="wiki-empty">
          <div className="empty-icon">
            <Icon name="book" width={28} height={28} />
          </div>
          <h2>
            {query ? "Keine passenden Artikel." : "Hier wächst unser Wissen."}
          </h2>
          <p>
            {query
              ? "Versuche einen anderen Suchbegriff oder setze die Filter zurück."
              : "Für diesen Zugang sind derzeit noch keine veröffentlichten Artikel verfügbar."}
          </p>
          {!session.authenticated && (
            <Link href="/login" className="text-link">
              Mit deinem Konto anmelden{" "}
              <Icon name="arrow" width={15} height={15} />
            </Link>
          )}
        </section>
      )}
    </main>
  );
}
