"use client";

import { useState } from "react";
import { Icon } from "@/components/ui/icon";
import type { Session } from "@/lib/auth";

export function LogoutButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setBusy(true);
    setError("");
    try {
      const sessionResponse = await fetch("/api/auth/session/", {
        cache: "no-store",
      });
      if (!sessionResponse.ok) throw new Error();
      const session: Session = await sessionResponse.json();
      const response = await fetch("/api/auth/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": session.csrfToken },
      });
      if (!response.ok) throw new Error();
      window.location.assign("/login");
    } catch {
      setError("Abmelden fehlgeschlagen. Bitte erneut versuchen.");
      setBusy(false);
    }
  }
  return (
    <>
      <button className="logout-button" onClick={logout} disabled={busy}>
        <Icon name="logout" />
        {busy ? "Wird abgemeldet …" : "Abmelden"}
      </button>
      {error && (
        <p className="helper" role="alert">
          {error}
        </p>
      )}
    </>
  );
}
