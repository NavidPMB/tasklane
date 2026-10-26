"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { sessionPost } from "@/lib/work";
export function AccountSettings({
  firstName,
  lastName,
  hasPassword,
}: {
  firstName: string;
  lastName: string;
  hasPassword: boolean;
}) {
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const router = useRouter();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await sessionPost(
        "/api/auth/account/",
        Object.fromEntries(new FormData(form)),
      );
      if (form.hasAttribute("data-password")) form.reset();
      setNotice("Gespeichert.");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Änderung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="tasklane-app">
      {error && (
        <p role="alert" className="tl-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <section className="tl-workspace-panel">
        <h2>Profil bearbeiten</h2>
        <form className="tl-form" onSubmit={save}>
          <div className="tl-form-grid">
            <label>
              Vorname
              <input
                name="first_name"
                defaultValue={firstName}
                maxLength={150}
                autoComplete="given-name"
              />
            </label>
            <label>
              Nachname
              <input
                name="last_name"
                defaultValue={lastName}
                maxLength={150}
                autoComplete="family-name"
              />
            </label>
          </div>
          <div>
            <button className="button" disabled={busy}>
              Profil speichern
            </button>
          </div>
        </form>
      </section>
      <section className="tl-workspace-panel">
        <h2>Passwort ändern</h2>
        {hasPassword ? (
          <form className="tl-form" onSubmit={save} data-password>
            <label>
              Aktuelles Passwort
              <input
                name="current_password"
                type="password"
                required
                autoComplete="current-password"
                maxLength={4096}
              />
            </label>
            <div className="tl-form-grid">
              <label>
                Neues Passwort
                <input
                  name="new_password"
                  type="password"
                  required
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={4096}
                />
              </label>
              <label>
                Neues Passwort wiederholen
                <input
                  name="confirm_password"
                  type="password"
                  required
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={4096}
                />
              </label>
            </div>
            <div>
              <button className="button" disabled={busy}>
                Passwort speichern
              </button>
            </div>
          </form>
        ) : (
          <p className="tl-hint">
            Dieses Konto verwendet die externe Anmeldung. Ein eigenes Passwort
            kann die Kontoverwaltung einrichten.
          </p>
        )}
      </section>
    </div>
  );
}
