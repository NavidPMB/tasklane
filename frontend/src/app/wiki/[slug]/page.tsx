import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { VisibilityBadge } from "@/components/wiki/visibility-badge";
import { WikiMarkdown } from "@/components/wiki/markdown";
import { getSession } from "@/lib/auth";
import { getArticle } from "@/lib/wiki";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const article = await getArticle((await params).slug);
  return {
    title: article.title,
    robots: {
      index: article.visibility === "public",
      follow: article.visibility === "public",
    },
  };
}

export default async function WikiArticlePage({ params }: Props) {
  const article = await getArticle((await params).slug);
  const session = await getSession();
  const updated = new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeZone: "Europe/Berlin",
  }).format(new Date(article.updatedAt));
  return (
    <main id="wiki-content" className="wiki-container wiki-detail">
      <div className="wiki-article-toolbar">
        <Link href="/wiki" className="text-link">
          ← Alle Wiki-Artikel
        </Link>
        {session.user?.isSuperuser && (
          <a
            href={`/django-admin/wiki/article/${article.id}/change/`}
            className="text-link"
          >
            Artikel bearbeiten <Icon name="arrow" width={15} height={15} />
          </a>
        )}
      </div>
      <div className="wiki-reading-layout">
        <aside
          className="wiki-reading-sidebar"
          aria-label="Artikelinformationen"
        >
          <div className="wiki-reading-label">
            <Icon name="book" />
            <span>Wiki</span>
          </div>
          <VisibilityBadge visibility={article.visibility} />
          <p>
            Aktualisiert am
            <br />
            <time dateTime={article.updatedAt}>{updated}</time>
          </p>
          <Link href="/wiki" className="text-link">
            Weitere Artikel entdecken
          </Link>
        </aside>
        <article className="wiki-article">
          <header className="wiki-article-header">
            <p className="eyebrow">Anleitung & Dokumentation</p>
            <h1>{article.title}</h1>
            {article.summary && <p>{article.summary}</p>}
          </header>
          <WikiMarkdown>{article.body}</WikiMarkdown>
        </article>
      </div>
    </main>
  );
}
