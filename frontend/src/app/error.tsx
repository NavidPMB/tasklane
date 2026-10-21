"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="error-page">
      <h1>Gerade nicht erreichbar.</h1>
      <p>Bitte versuche es in einem Moment erneut.</p>
      <button className="button" onClick={reset}>
        Erneut versuchen
      </button>
      <a href="/" className="text-link">
        Zur Startseite
      </a>
    </main>
  );
}
