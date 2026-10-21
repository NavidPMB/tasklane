"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { type Workspace, workFetch, workAction } from "@/lib/work";

type Connection = { base_url: string; email: string; configured: boolean };
type Issue = {
  id: string;
  key: string;
  title: string;
  project: string;
  status: string;
  kind: string;
  parent_key: string | null;
  imported: boolean;
};
type Preview = { issues: Issue[]; next_page_token: string | null };
type Result = {
  created: string[];
  skipped: string[];
  projects_created: { id: number; name: string; key: string }[];
  warnings: string[];
};
export function JiraImport({
  initialWorkspace,
}: {
  initialWorkspace?: number;
}) {
  const [spaces, setSpaces] = useState<Workspace[]>([]),
    [workspace, setWorkspace] = useState(initialWorkspace || 0);
  const [connection, setConnection] = useState<Connection | null>(null),
    [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [jql, setJql] = useState(
      "assignee = currentUser() ORDER BY updated DESC",
    ),
    [searchedJql, setSearchedJql] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]),
    [next, setNext] = useState<string | null>(null),
    [selection, setSelection] = useState<string[]>([]),
    [hasSearched, setHasSearched] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const version = useRef(0);
  const current = spaces.find((w) => w.id === workspace);
  useEffect(() => {
    const controller = new AbortController();
    workFetch<{ workspaces: Workspace[] }>(
      "/api/work/workspaces/",
      controller.signal,
    )
      .then((r) => {
        setSpaces(r.workspaces);
        setWorkspace((id) =>
          r.workspaces.some((w) => w.id === id)
            ? id
            : r.workspaces.find((w) => w.can_manage)?.id || 0,
        );
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const request = ++version.current;
    setReady(false);
    setConnection(null);
    setIssues([]);
    setSelection([]);
    setResult(null);
    setHasSearched(false);
    setNext(null);
    setError("");
    setNotice("");
    if (!workspace || !current?.can_manage) return;
    workAction<{ connection: Connection | null }>("get_jira_connection", {
      workspace_id: workspace,
    })
      .then((r) => {
        if (version.current === request) {
          setConnection(r.connection);
          setReady(true);
        }
      })
      .catch((err) => {
        if (version.current === request) setError(err.message);
      });
    return () => {
      version.current++;
    };
  }, [workspace, current?.can_manage]);
  async function configure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await workAction<{ connection: Connection }>(
        "configure_jira",
        { workspace_id: workspace, ...Object.fromEntries(new FormData(form)) },
      );
      setConnection(data.connection);
      form.reset();
      setNotice("Jira-Verbindung geprüft und gespeichert.");
      setIssues([]);
      setSelection([]);
      setNext(null);
      setHasSearched(false);
      setResult(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Verbindung fehlgeschlagen.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function search(more = false) {
    setBusy(true);
    setError("");
    setNotice("");
    if (!more) {
      setIssues([]);
      setSelection([]);
      setResult(null);
      setHasSearched(false);
      setNext(null);
    }
    try {
      const query = more ? searchedJql : jql;
      const data = await workAction<Preview>("preview_jira", {
        workspace_id: workspace,
        jql: query,
        ...(more && next ? { next_page_token: next } : {}),
      });
      setIssues((old) =>
        more
          ? [
              ...old,
              ...data.issues.filter(
                (item) => !old.some((existing) => existing.id === item.id),
              ),
            ]
          : data.issues,
      );
      setNext(data.next_page_token);
      setSearchedJql(query);
      setHasSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suche fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  async function importSelected() {
    setBusy(true);
    setError("");
    setNotice("");
    setResult(null);
    try {
      const data = await workAction<Result>("import_jira", {
        workspace_id: workspace,
        issue_keys: selection,
      });
      setResult(data);
      const imported = new Set([...data.created, ...data.skipped]);
      setIssues((old) =>
        old.map((i) => (imported.has(i.key) ? { ...i, imported: true } : i)),
      );
      setSelection([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  function toggle(key: string) {
    setSelection((old) =>
      old.includes(key)
        ? old.filter((k) => k !== key)
        : old.length < 50
          ? [...old, key]
          : old,
    );
  }
  return (
    <div className="tasklane-app tl-jira-page" aria-busy={busy}>
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">JIRA CLOUD → TASKLANE</p>
          <h1>Tickets mitnehmen. Gemeinsam weiterarbeiten.</h1>
          <p>
            Workspace wählen, Jira verbinden und die gewünschten Tickets
            importieren.
          </p>
        </div>
        <Link className="tl-secondary" href="/dashboard/workspaces">
          Workspaces & Team
        </Link>
      </div>
      <div className="tl-workspace-bar">
        <label>
          Ziel-Workspace
          <select
            value={workspace}
            aria-label="Ziel-Workspace"
            disabled={busy}
            onChange={(e) => setWorkspace(Number(e.target.value))}
          >
            <option value={0}>Workspace wählen</option>
            {spaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
                {w.can_manage ? "" : " · nur Lesen"}
              </option>
            ))}
          </select>
        </label>
        {current && (
          <span className="tl-hint">
            Projekte werden automatisch in {current.name} angelegt.
          </span>
        )}
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
      {!workspace ? (
        <section className="tl-workspace-panel">
          <p>Wähle einen Workspace oder erstelle zuerst einen für dein Team.</p>
          <Link className="button" href="/dashboard/workspaces">
            Workspace erstellen
          </Link>
        </section>
      ) : !current?.can_manage ? (
        <p className="tl-hint">
          Die Workspace-Leitung verwaltet die Jira-Verbindung und den Import.
          Importierte Projekte stehen anschließend allen Workspace-Mitgliedern
          zur Verfügung.
        </p>
      ) : !ready ? (
        <p>Verbindung wird geladen …</p>
      ) : (
        <>
          <section className="tl-workspace-panel">
            <div className="tl-panel-head">
              <h2>1. Jira verbinden</h2>
              <span
                className={
                  connection?.configured ? "tl-success-label" : "tl-hint"
                }
              >
                {connection?.configured
                  ? "✓ Verbindung eingerichtet"
                  : "Noch nicht verbunden"}
              </span>
            </div>
            <p className="tl-hint">
              Verwende einen Jira-Cloud-API-Token für deine Site. Tokens mit und
              ohne Scopes werden unterstützt.{" "}
              <a
                href="https://id.atlassian.com/manage-profile/security/api-tokens"
                target="_blank"
                rel="noreferrer"
              >
                API-Token bei Atlassian erstellen ↗
              </a>
            </p>
            <form
              key={`${workspace}-${connection?.base_url}-${connection?.email}`}
              className="tl-form"
              onSubmit={configure}
              autoComplete="off"
            >
              <div className="tl-jira-credentials">
                <label>
                  Jira-Cloud-Adresse
                  <input
                    name="base_url"
                    type="url"
                    required
                    maxLength={250}
                    placeholder="https://dein-team.atlassian.net"
                    defaultValue={connection?.base_url || ""}
                  />
                </label>
                <label>
                  Jira-E-Mail
                  <input
                    name="email"
                    type="email"
                    required
                    maxLength={254}
                    defaultValue={connection?.email || ""}
                    placeholder="name@dein-team.de"
                  />
                </label>
                <label>
                  API-Token
                  <input
                    name="api_token"
                    type="password"
                    required
                    maxLength={2000}
                    autoComplete="new-password"
                    placeholder={
                      connection ? "Neuen Token eingeben" : "API-Token eingeben"
                    }
                  />
                </label>
              </div>
              <p className="tl-hint">
                Der Token wird verschlüsselt auf dem Server gespeichert und nach
                dem Speichern nicht angezeigt. Nur die Workspace-Leitung kann
                die Verbindung verwalten.
              </p>
              <div>
                <button className="tl-secondary" disabled={busy}>
                  {busy ? "Bitte warten …" : "Verbindung prüfen & speichern"}
                </button>
              </div>
            </form>
          </section>
          {connection?.configured && (
            <section className="tl-workspace-panel">
              <h2>2. Tickets suchen</h2>
              <form
                className="tl-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void search();
                }}
              >
                <label>
                  JQL-Suche
                  <textarea
                    value={jql}
                    onChange={(e) => setJql(e.target.value)}
                    maxLength={2000}
                    required
                    rows={2}
                  />
                </label>
                <p className="tl-hint">
                  Zum Beispiel:{" "}
                  <code>project in (WEB, APP) ORDER BY updated DESC</code>. Die
                  Vorschau lädt jeweils bis zu 50 Tickets.
                </p>
                <div>
                  <button className="button" disabled={busy || !jql.trim()}>
                    {busy ? "Bitte warten …" : "Vorschau laden"}
                  </button>
                </div>
              </form>
            </section>
          )}
          {hasSearched && (
            <section className="tl-workspace-panel">
              <div className="tl-panel-head">
                <h2>3. Tickets auswählen & importieren</h2>
                <strong>{selection.length} / 50 ausgewählt</strong>
              </div>
              <p className="tl-hint">
                Neue Projekte, Status und Tags entstehen automatisch. Wähle
                Eltern-Tickets und Epics ebenfalls aus, wenn die Hierarchie
                übernommen werden soll. Bereits importierte Tickets werden
                übersprungen.
              </p>
              <div className="tl-import-actions">
                <button
                  className="tl-secondary"
                  disabled={busy || !issues.some((i) => !i.imported)}
                  onClick={() =>
                    setSelection(
                      issues
                        .filter((i) => !i.imported)
                        .slice(0, 50)
                        .map((i) => i.key),
                    )
                  }
                >
                  Bis zu 50 auswählen
                </button>
                <button
                  className="tl-plain-button"
                  disabled={busy || !selection.length}
                  onClick={() => setSelection([])}
                >
                  Auswahl aufheben
                </button>
              </div>
              <div className="tl-jira-table-wrap">
                <table className="tl-jira-table">
                  <thead>
                    <tr>
                      <th>
                        <span className="sr-only">Auswahl</span>
                      </th>
                      <th>Ticket</th>
                      <th>Projekt</th>
                      <th>Status</th>
                      <th>Typ / Eltern-Ticket</th>
                    </tr>
                  </thead>
                  <tbody>
                    {issues.map((i) => (
                      <tr key={i.id}>
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`${i.key} auswählen`}
                            checked={selection.includes(i.key)}
                            disabled={
                              busy ||
                              i.imported ||
                              (!selection.includes(i.key) &&
                                selection.length >= 50)
                            }
                            onChange={() => toggle(i.key)}
                          />
                        </td>
                        <td>
                          <strong>{i.key}</strong>
                          {i.imported && (
                            <span className="tl-base-label">
                              Bereits importiert
                            </span>
                          )}
                          <span>{i.title}</span>
                        </td>
                        <td>{i.project}</td>
                        <td>{i.status}</td>
                        <td>
                          {i.kind}
                          {i.parent_key && <small>Unter {i.parent_key}</small>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!issues.length && (
                <p className="tl-hint">
                  Keine Tickets für diese Suche gefunden.
                </p>
              )}
              <div className="tl-import-actions">
                {next && (
                  <button
                    className="tl-secondary"
                    disabled={busy}
                    onClick={() => void search(true)}
                  >
                    Weitere Tickets laden
                  </button>
                )}
                <button
                  className="button"
                  disabled={busy || !selection.length}
                  onClick={() => void importSelected()}
                >
                  {busy
                    ? "Bitte warten …"
                    : `${selection.length} Tickets nach ${current.name} importieren`}
                </button>
              </div>
            </section>
          )}
          {result && (
            <section className="tl-workspace-panel" role="status">
              <h2>Import abgeschlossen</h2>
              <p>
                {result.created.length} Tickets importiert ·{" "}
                {result.skipped.length} bereits vorhanden ·{" "}
                {result.projects_created.length} Projekte angelegt
              </p>
              {result.projects_created.map((p) => (
                <p key={p.id}>
                  <Link
                    href={`/dashboard?workspace=${workspace}&project=${p.id}`}
                  >
                    {p.key} · {p.name} öffnen →
                  </Link>
                </p>
              ))}
              {result.warnings.length > 0 && (
                <>
                  <h3>Hinweise zur Zuordnung</h3>
                  <ul>
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </>
              )}
              <Link
                href={`/dashboard/projects?workspace=${workspace}`}
                className="button"
              >
                Projekte im Workspace öffnen
              </Link>
            </section>
          )}
        </>
      )}
    </div>
  );
}
