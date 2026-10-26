"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { type Workspace, sessionPost, workFetch } from "@/lib/work";
type Token = {
  id: number;
  name: string;
  scope: "read" | "write" | "manage";
  workspace_id: number | null;
  expires_at: string;
  revoked: boolean;
  last_used_at: string | null;
};
const scopeLabels = {
  read: "Nur lesen",
  write: "Lesen & schreiben",
  manage: "Mitglieder & Integrationen verwalten",
};
export function IntegrationAccess({ publicUrl }: { publicUrl: string }) {
  const [tokens, setTokens] = useState<Token[]>([]),
    [spaces, setSpaces] = useState<Workspace[]>([]),
    [secret, setSecret] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    const [t, w] = await Promise.all([
      workFetch<{ tokens: Token[] }>("/api/work/access-tokens/"),
      workFetch<{ workspaces: Workspace[] }>("/api/work/workspaces/"),
    ]);
    setTokens(t.tokens);
    setSpaces(w.workspaces);
  }, []);
  useEffect(() => {
    let mounted = true;
    load().catch((e) => {
      if (mounted) setError(e.message);
    });
    return () => {
      mounted = false;
    };
  }, [load]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget,
      values = new FormData(form);
    setBusy(true);
    setError("");
    setSecret("");
    try {
      const result = await sessionPost<Token & { token: string }>(
        "/api/work/access-tokens/",
        {
          name: values.get("name"),
          scope: values.get("scope"),
          workspace_id: values.get("workspace")
            ? Number(values.get("workspace"))
            : null,
          expires_in_days: Number(values.get("days")),
        },
      );
      setSecret(result.token);
      form.reset();
      await load();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Schlüssel konnte nicht erstellt werden.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function revoke(token: Token) {
    if (
      !window.confirm(
        `Schlüssel „${token.name}“ widerrufen? Verbundene Anwendungen verlieren damit den Zugriff.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await sessionPost("/api/work/access-tokens/", { revoke_id: token.id });
      setSecret("");
      await load();
      setNotice("Schlüssel widerrufen.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Widerruf fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="tasklane-app">
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">ANDERE ANWENDUNGEN VERBINDEN</p>
          <h1>API & Remote-MCP</h1>
          <p>
            Verbinde Assistenten und andere Projekte mit deinem Tasklane-Konto.
          </p>
        </div>
      </div>
      {error && (
        <p className="tl-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <section className="tl-workspace-panel">
        <h2>Deine Verbindung</h2>
        <div className="tl-form-grid">
          <div>
            <h3>Remote-MCP</h3>
            <code className="tl-endpoint">{publicUrl}/mcp</code>
            <p className="tl-hint">
              Streamable HTTP mit einem persönlichen Bearer-Schlüssel. Dein
              MCP-Client sendet den Schlüssel im Authorization-Header.
            </p>
          </div>
          <div>
            <h3>Versionierte API</h3>
            <code className="tl-endpoint">{publicUrl}/api/v1</code>
            <p className="tl-hint">
              <a href="/api/v1/openapi.json" target="_blank" rel="noreferrer">
                OpenAPI-Beschreibung öffnen ↗
              </a>{" "}
              · Die API verwendet dieselben Rechte und Aktionen wie die
              Oberfläche.
            </p>
          </div>
        </div>
        <p className="tl-hint">
          Schlüssel gelten nur für dein Konto und die gewählten Rechte. Ein
          Workspace-Filter begrenzt den Zugriff zusätzlich. Entfernte
          Mitgliedschaften und gesperrte Konten werden bei jedem Aufruf neu
          geprüft.
        </p>
      </section>
      {secret && (
        <section className="tl-workspace-panel tl-secret-panel" role="status">
          <h2>Schlüssel einmalig sichern</h2>
          <p>
            Dieser Schlüssel wird nur jetzt angezeigt. Bewahre ihn im
            Secret-Speicher der verbundenen Anwendung auf.
          </p>
          <code className="tl-secret-value">{secret}</code>
          <div className="tl-import-actions">
            <button
              className="tl-secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(secret);
                  setNotice("Schlüssel kopiert.");
                } catch {
                  setError("Bitte den angezeigten Schlüssel manuell kopieren.");
                }
              }}
            >
              Schlüssel kopieren
            </button>
            <button className="button" onClick={() => setSecret("")}>
              Gesichert · ausblenden
            </button>
          </div>
        </section>
      )}
      <section className="tl-workspace-panel">
        <h2>Integrationsschlüssel erstellen</h2>
        <form className="tl-form" onSubmit={create}>
          <label>
            Name
            <input
              name="name"
              required
              maxLength={120}
              placeholder="Zum Beispiel: Mein Assistent"
            />
          </label>
          <div className="tl-form-grid">
            <label>
              Zugriff
              <select name="scope" aria-label="Zugriff" defaultValue="read">
                {Object.entries(scopeLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Workspace
              <select name="workspace" aria-label="Workspace">
                <option value="">
                  Alle für mein Konto zugänglichen Projekte
                </option>
                {spaces
                  .filter((w) => w.can_create_project)
                  .map((w) => (
                    <option value={w.id} key={w.id}>
                      {w.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Gültig für
              <select name="days" aria-label="Gültigkeit" defaultValue="90">
                {[1, 7, 30, 90, 365].map((days) => (
                  <option key={days} value={days}>
                    {days} Tage
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="tl-hint">
            „Lesen & schreiben“ erlaubt Ticketarbeit und Dateien.
            Mitgliederfreigaben und Integrationszugänge benötigen die
            zusätzliche Verwaltungsberechtigung. Deine eigenen Projekt- und
            Workspace-Rechte bleiben die Obergrenze.
          </p>
          <div>
            <button className="button" disabled={busy}>
              Schlüssel erstellen
            </button>
          </div>
        </form>
      </section>
      <section className="tl-workspace-panel">
        <h2>Bestehende Schlüssel</h2>
        {!tokens.length && (
          <p className="tl-hint">Noch keine Integrationsschlüssel erstellt.</p>
        )}
        <div className="tl-token-list">
          {tokens.map((token) => (
            <article key={token.id}>
              <div>
                <strong>{token.name}</strong>
                <p>
                  {scopeLabels[token.scope]} ·{" "}
                  {token.workspace_id
                    ? spaces.find((s) => s.id === token.workspace_id)?.name ||
                      "Workspace"
                    : "Alle zugänglichen Projekte"}
                </p>
                <small>
                  {token.revoked
                    ? "Widerrufen"
                    : new Date(token.expires_at) < new Date()
                      ? "Abgelaufen"
                      : `Gültig bis ${new Date(token.expires_at).toLocaleDateString("de-DE")}`}
                  {token.last_used_at
                    ? ` · Zuletzt genutzt ${new Date(token.last_used_at).toLocaleString("de-DE")}`
                    : " · Noch nicht genutzt"}
                </small>
              </div>
              {!token.revoked && (
                <button
                  className="tl-plain-button tl-danger"
                  disabled={busy}
                  onClick={() => void revoke(token)}
                >
                  Widerrufen
                </button>
              )}
            </article>
          ))}
        </div>
      </section>
      <section className="tl-workspace-panel">
        <h2>API-Beispiel</h2>
        <p className="tl-hint">
          Speichere den Schlüssel in der Serverumgebung deiner Anwendung als
          TASKLANE_API_TOKEN.
        </p>
        <pre className="tl-code-block">
          <code>{`curl '${publicUrl}/api/v1/projects' \\\n  -H "Authorization: Bearer $TASKLANE_API_TOKEN"\n\ncurl '${publicUrl}/api/v1/actions/create_ticket' \\\n  -H "Authorization: Bearer $TASKLANE_API_TOKEN" \\\n  -H 'Content-Type: application/json' \\\n  --data '{"project_id": 1, "title": "Ticket aus meiner Anwendung"}'`}</code>
        </pre>
        <p className="tl-hint">
          Projekt- und Status-IDs zuerst aus den zugänglichen Daten lesen. Keine
          fremde Identität als Parameter übergeben. Schlüssel gehören in die
          Serverumgebung der Integration, nicht in Browser-Speicher oder
          öffentliches Frontend.
        </p>
      </section>
      <section className="tl-workspace-panel">
        <h2>Lokales MCP über stdio</h2>
        <p>
          Für einen lokalen Checkout bleibt die bestehende Verbindung verfügbar.
          Starte PostgreSQL und erzeuge auf deinem Rechner die passende
          Konfiguration:
        </p>
        <pre className="tl-code-block">
          <code>make mcp-config MCP_EMAIL=deine-adresse@example.com</code>
        </pre>
        <p className="tl-hint">
          Für den Zugriff auf diese Domain verwende den Remote-MCP-Endpunkt
          oben. Die lokale stdio-Verbindung benötigt einen eigenen Checkout mit
          Datenbankzugriff.
        </p>
      </section>
    </div>
  );
}
