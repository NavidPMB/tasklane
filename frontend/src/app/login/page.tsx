import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { GoogleSignIn } from "@/components/auth/google-sign-in";
import { PasswordSignIn } from "@/components/auth/password-sign-in";
import { project } from "@/config/project";
import { getSession } from "@/lib/auth";

export const metadata: Metadata = { title: "Anmelden" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const session = await getSession();
  if (session.authenticated) redirect("/dashboard");
  const { error } = await searchParams;
  return (
    <main className="login-page">
      <Link className="login-back text-link" href="/">
        ← Zur Website
      </Link>
      <div className="login-card">
        <span className="brand-mark">{project.monogram}</span>
        <p className="eyebrow">{project.name}</p>
        <h1>Willkommen zurück.</h1>
        <p>Melde dich an und öffne deinen Arbeitsbereich.</p>
        {error && (
          <p className="notice" role="alert">
            {error === "unverified-email"
              ? "Bitte verwende ein Google-Konto mit bestätigter E-Mail-Adresse."
              : "Die Google-Anmeldung ist gerade nicht verfügbar."}
          </p>
        )}
        <PasswordSignIn />
        {session.googleLoginEnabled && (
          <>
            <div className="login-divider">
              <span>oder</span>
            </div>
            <GoogleSignIn />
          </>
        )}
        <div className="login-footnote">Dein Konto. Dein Arbeitsbereich.</div>
      </div>
      <span className="login-brand">{project.name}</span>
    </main>
  );
}
