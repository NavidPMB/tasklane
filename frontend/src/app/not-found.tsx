import Link from "next/link";

export default function NotFound() {
  return (
    <main className="error-page">
      <p className="eyebrow">404</p>
      <h1>Hier ist noch kein Inhalt.</h1>
      <p>Die gesuchte Seite wurde nicht gefunden.</p>
      <Link href="/" className="button">
        Zur Startseite
      </Link>
    </main>
  );
}
