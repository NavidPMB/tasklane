"use client";

import { useEffect, useState } from "react";
import type { Session } from "@/lib/auth";

export function GoogleSignIn() {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/auth/session/", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .then(setSession)
      .catch((error: Error) => {
        if (error.name !== "AbortError")
          setError("Die Anmeldung ist gerade nicht erreichbar.");
      });
    return () => controller.abort();
  }, []);

  return (
    <>
      <form action="/accounts/google/login/" method="post">
        <input
          type="hidden"
          name="csrfmiddlewaretoken"
          value={session?.csrfToken || ""}
        />
        <button
          className="button google-button"
          type="submit"
          disabled={!session?.googleLoginEnabled}
        >
          <svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true">
            <path
              fill="currentColor"
              d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.36ZM12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.05.97-3.38.97-2.6 0-4.8-1.76-5.59-4.12H3.06v2.59A10 10 0 0 0 12 22ZM6.41 13.93a6 6 0 0 1 0-3.86V7.48H3.06a10 10 0 0 0 0 9.04l3.35-2.59ZM12 5.95c1.47 0 2.79.51 3.82 1.51l2.87-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.48l3.35 2.59A6 6 0 0 1 12 5.95Z"
            />
          </svg>
          Mit Google anmelden
        </button>
      </form>
      <p className="helper" role="status">
        {error ||
          (session && !session.googleLoginEnabled
            ? "Die Google-Anmeldung wird gerade eingerichtet."
            : !session
              ? "Anmeldung wird vorbereitet …"
              : "Sicher mit deinem Google-Konto fortfahren.")}
      </p>
    </>
  );
}
