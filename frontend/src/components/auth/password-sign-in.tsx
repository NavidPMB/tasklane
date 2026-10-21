"use client";

import { useState, type FormEvent } from "react";

export function PasswordSignIn() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const sessionResponse = await fetch("/api/auth/session/", {
        cache: "no-store",
      });
      if (!sessionResponse.ok)
        throw new Error("Die Anmeldung ist gerade nicht erreichbar.");
      const session = await sessionResponse.json();
      const response = await fetch("/api/auth/login/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": session.csrfToken,
        },
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      const result = await response.json().catch(() => {
        throw new Error(
          "Die Anmeldung ist gerade nicht erreichbar. Bitte erneut versuchen.",
        );
      });
      if (!response.ok)
        throw new Error(result.error || "Anmeldung fehlgeschlagen.");
      window.location.assign("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.",
      );
      setBusy(false);
    }
  }

  return (
    <form
      className="password-login-form"
      onSubmit={submit}
      aria-label="Mit E-Mail und Passwort anmelden"
    >
      <label htmlFor="login-email">E-Mail-Adresse</label>
      <input
        id="login-email"
        name="email"
        type="email"
        autoComplete="username"
        required
        maxLength={254}
        placeholder="name@beispiel.de"
        disabled={busy}
        autoCapitalize="none"
        spellCheck={false}
      />
      <label htmlFor="login-password">Passwort</label>
      <input
        id="login-password"
        name="password"
        type="password"
        autoComplete="current-password"
        required
        maxLength={4096}
        disabled={busy}
        aria-describedby={error ? "password-login-error" : undefined}
      />
      {error && (
        <p
          id="password-login-error"
          className="password-login-error"
          role="alert"
        >
          {error}
        </p>
      )}
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Anmeldung läuft …" : "Anmelden"}
      </button>
    </form>
  );
}
