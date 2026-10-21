"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { type Workspace, workFetch, workAction } from "@/lib/work";
import { formatMinutes, displayDate } from "@/lib/time";

type Location = { id: string; name: string };
type Locations = {
  teams: Location[];
  spaces: Location[];
  folders: Location[];
  lists: Location[];
};
type Connection = { account_name: string; configured: boolean };
type Task = {
  id: string;
  title: string;
  status: string;
  completed: boolean;
  parent_id: string | null;
  minutes: number;
  list_name: string;
  imported: boolean;
};
type Plan = {
  batch_id: string;
  expires_at: string;
  prepared_at: string;
  task_count: number;
  entry_count: number;
  total_minutes: number;
  timezone: string;
  warnings: string[];
  date_from: string | null;
  date_to: string | null;
  people: {
    id: string;
    name: string;
    email: string;
    minutes: number;
    entry_count: number;
  }[];
};
type Result = {
  created: string[];
  skipped: string[];
  projects_created: { id: number; name: string; key: string }[];
  time_entries_created: number;
  time_entries_skipped: number;
  imported_minutes: number;
  warnings: string[];
  date_from: string | null;
  date_to: string | null;
};

export function ClickUpImport({
  initialWorkspace,
}: {
  initialWorkspace?: number;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [workspace, setWorkspace] = useState(initialWorkspace || 0);
  const [connection, setConnection] = useState<Connection | null>(null),
    [ready, setReady] = useState(false),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [teams, setTeams] = useState<Location[]>([]),
    [spaces, setSpaces] = useState<Location[]>([]),
    [folders, setFolders] = useState<Location[]>([]),
    [lists, setLists] = useState<Location[]>([]),
    [folderless, setFolderless] = useState<Location[]>([]);
  const [team, setTeam] = useState(""),
    [space, setSpace] = useState(""),
    [folder, setFolder] = useState(""),
    [list, setList] = useState("");
  const [archivedLocations, setArchivedLocations] = useState(false),
    [archivedTasks, setArchivedTasks] = useState(false),
    [onlyCompleted, setOnlyCompleted] = useState(true);
  const [tasks, setTasks] = useState<Task[]>([]),
    [selection, setSelection] = useState<Task[]>([]),
    [next, setNext] = useState<number | null>(null),
    [searched, setSearched] = useState(false);
  const [plan, setPlan] = useState<Plan | null>(null),
    [result, setResult] = useState<Result | null>(null);
  const version = useRef(0);
  const current = workspaces.find((w) => w.id === workspace);
  useEffect(() => {
    const controller = new AbortController();
    workFetch<{ workspaces: Workspace[] }>(
      "/api/work/workspaces/",
      controller.signal,
    )
      .then((r) => {
        setWorkspaces(r.workspaces);
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
    setTeams([]);
    setSpaces([]);
    setFolders([]);
    setLists([]);
    setTeam("");
    setSpace("");
    setFolder("");
    setList("");
    setTasks([]);
    setSelection([]);
    setPlan(null);
    setResult(null);
    setError("");
    setNotice("");
    setSearched(false);
    setNext(null);
    if (!workspace || !current?.can_manage) return;
    (async () => {
      const c = await workAction<{ connection: Connection | null }>(
        "get_clickup_connection",
        { workspace_id: workspace },
      );
      if (request !== version.current) return;
      setConnection(c.connection);
      setReady(true);
      const locations = c.connection?.configured
        ? await workAction<Locations>("list_clickup_locations", {
            workspace_id: workspace,
          })
        : null;
      if (request === version.current) setTeams(locations?.teams || []);
    })().catch((err) => {
      if (request === version.current) setError(err.message);
    });
    return () => {
      version.current++;
    };
  }, [workspace, current?.can_manage]);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anfrage fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  function clearTasks() {
    setTasks([]);
    setNext(null);
    setSearched(false);
    setPlan(null);
    setResult(null);
  }
  async function configure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    await run(async () => {
      const response = await workAction<{ connection: Connection }>(
        "configure_clickup",
        { workspace_id: workspace, ...Object.fromEntries(new FormData(form)) },
      );
      form.reset();
      setConnection(response.connection);
      setTeam("");
      setSpace("");
      setFolder("");
      setList("");
      setSpaces([]);
      setFolders([]);
      setLists([]);
      setSelection([]);
      clearTasks();
      const r = await workAction<Locations>("list_clickup_locations", {
        workspace_id: workspace,
      });
      setTeams(r.teams);
      setNotice("ClickUp-Verbindung geprüft und verschlüsselt gespeichert.");
    });
  }
  async function chooseTeam(id: string, archived = archivedLocations) {
    setTeam(id);
    setSpace("");
    setFolder("");
    setList("");
    setSpaces([]);
    setFolders([]);
    setLists([]);
    setFolderless([]);
    setSelection([]);
    clearTasks();
    if (id)
      await run(async () => {
        const r = await workAction<Locations>("list_clickup_locations", {
          workspace_id: workspace,
          team_id: id,
          archived,
        });
        setSpaces(r.spaces);
      });
  }
  async function chooseSpace(id: string) {
    setSpace(id);
    setFolder("");
    setList("");
    setFolders([]);
    setLists([]);
    setFolderless([]);
    clearTasks();
    if (id)
      await run(async () => {
        const r = await workAction<Locations>("list_clickup_locations", {
          workspace_id: workspace,
          team_id: team,
          space_id: id,
          archived: archivedLocations,
        });
        setFolders(r.folders);
        setLists(r.lists);
        setFolderless(r.lists);
      });
  }
  async function chooseFolder(id: string) {
    setFolder(id);
    setList("");
    setLists([]);
    clearTasks();
    if (!id) {
      setLists(folderless);
      return;
    }
    await run(async () => {
      const r = await workAction<Locations>("list_clickup_locations", {
        workspace_id: workspace,
        team_id: team,
        space_id: space,
        folder_id: id,
        archived: archivedLocations,
      });
      setLists(r.lists);
    });
  }
  async function preview(more = false) {
    if (!more) clearTasks();
    await run(async () => {
      const r = await workAction<{ tasks: Task[]; next_page: number | null }>(
        "preview_clickup",
        {
          workspace_id: workspace,
          team_id: team,
          list_id: list,
          page: more ? next || 0 : 0,
          archived: archivedTasks,
          only_completed: onlyCompleted,
        },
      );
      setTasks((old) =>
        more
          ? [
              ...old,
              ...r.tasks.filter(
                (t) => !old.some((existing) => existing.id === t.id),
              ),
            ]
          : r.tasks,
      );
      setNext(r.next_page);
      setSearched(true);
    });
  }
  function toggle(task: Task) {
    setPlan(null);
    setResult(null);
    setSelection((old) =>
      old.some((t) => t.id === task.id)
        ? old.filter((t) => t.id !== task.id)
        : old.length < 20
          ? [...old, task]
          : old,
    );
  }
  async function prepare() {
    setPlan(null);
    setResult(null);
    await run(async () => {
      const r = await workAction<Plan>("prepare_clickup_import", {
        workspace_id: workspace,
        team_id: team,
        task_ids: selection.map((t) => t.id),
      });
      setPlan(r);
    });
  }
  async function commit() {
    if (!plan) return;
    await run(async () => {
      const r = await workAction<Result>("import_clickup", {
        workspace_id: workspace,
        batch_id: plan.batch_id,
      });
      setResult(r);
      setPlan(null);
      setSelection([]);
      setTasks((old) =>
        old.map((t) =>
          r.created.includes(t.id) || r.skipped.includes(t.id)
            ? { ...t, imported: true }
            : t,
        ),
      );
    });
  }
  const reportQuery = new URLSearchParams({
    workspace: String(workspace),
    ...(result?.date_from ? { date_from: result.date_from } : {}),
    ...(result?.date_to ? { date_to: result.date_to } : {}),
  });
  return (
    <div className="tasklane-app tl-clickup-page" aria-busy={busy}>
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">CLICKUP → TASKLANE</p>
          <h1>Abgeschlossene Arbeit. Mit ihrer ganzen Zeithistorie.</h1>
          <p>
            Importiere ClickUp-Aufgaben und bereits gebuchte Arbeitszeiten in
            deinen Workspace.
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
            aria-label="Ziel-Workspace"
            value={workspace}
            disabled={busy}
            onChange={(e) => setWorkspace(Number(e.target.value))}
          >
            <option value={0}>Workspace wählen</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
                {w.can_manage ? "" : " · nur Lesen"}
              </option>
            ))}
          </select>
        </label>
        <span className="tl-hint">
          ClickUp-Listen werden automatisch zu Projekten im Ziel-Workspace.
        </span>
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
          <p>
            Erstelle zuerst einen Workspace oder wähle einen bestehenden aus.
          </p>
          <Link href="/dashboard/workspaces" className="button">
            Workspace erstellen
          </Link>
        </section>
      ) : !current?.can_manage ? (
        <p className="tl-hint">
          Die Workspace-Leitung verwaltet ClickUp und den Import. Projekte und
          importierte Zeitberichte stehen danach dem Workspace-Team zur
          Verfügung.
        </p>
      ) : !ready ? (
        <p>ClickUp-Verbindung wird geladen …</p>
      ) : (
        <>
          <section className="tl-workspace-panel">
            <div className="tl-panel-head">
              <h2>1. ClickUp verbinden</h2>
              <span className="tl-success-label">
                {connection?.configured
                  ? `✓ Verbunden als ${connection.account_name}`
                  : "Noch nicht verbunden"}
              </span>
            </div>
            <form className="tl-form" onSubmit={configure} autoComplete="off">
              <label>
                Persönlicher ClickUp-API-Token
                <input
                  name="api_token"
                  type="password"
                  required
                  maxLength={2000}
                  autoComplete="new-password"
                  placeholder="pk_…"
                />
              </label>
              <p className="tl-hint">
                Den Token findest du in{" "}
                <a
                  href="https://app.clickup.com/settings/apps"
                  target="_blank"
                  rel="noreferrer"
                >
                  ClickUp → Einstellungen → Apps ↗
                </a>
                . Für die Zeitbuchungen anderer Personen benötigst du in ClickUp
                Workspace-Owner- oder Admin-Rechte. Der Token wird zentral
                verschlüsselt gespeichert und nicht angezeigt.
              </p>
              <div>
                <button className="tl-secondary" disabled={busy}>
                  Verbindung prüfen & speichern
                </button>
              </div>
            </form>
          </section>
          {connection?.configured && (
            <section className="tl-workspace-panel">
              <h2>2. Aufgaben auswählen</h2>
              <div className="tl-clickup-locations">
                <label>
                  ClickUp-Workspace
                  <select
                    aria-label="ClickUp-Workspace"
                    value={team}
                    disabled={busy}
                    onChange={(e) => void chooseTeam(e.target.value)}
                  >
                    <option value="">Workspace wählen</option>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Space
                  <select
                    aria-label="ClickUp-Space"
                    value={space}
                    disabled={busy || !team}
                    onChange={(e) => void chooseSpace(e.target.value)}
                  >
                    <option value="">Space wählen</option>
                    {spaces.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Ordner
                  <select
                    aria-label="ClickUp-Ordner"
                    value={folder}
                    disabled={busy || !space}
                    onChange={(e) => void chooseFolder(e.target.value)}
                  >
                    <option value="">Listen ohne Ordner</option>
                    {folders.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Liste
                  <select
                    aria-label="ClickUp-Liste"
                    value={list}
                    disabled={busy || !space}
                    onChange={(e) => {
                      setList(e.target.value);
                      clearTasks();
                    }}
                  >
                    <option value="">Liste wählen</option>
                    {lists.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="tl-clickup-options">
                <label>
                  <input
                    type="checkbox"
                    checked={archivedLocations}
                    disabled={busy}
                    onChange={(e) => {
                      setArchivedLocations(e.target.checked);
                      void chooseTeam(team, e.target.checked);
                    }}
                  />
                  Archivierte Bereiche anzeigen
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={archivedTasks}
                    disabled={busy}
                    onChange={(e) => {
                      setArchivedTasks(e.target.checked);
                      clearTasks();
                    }}
                  />
                  Archivierte Aufgaben anzeigen
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={onlyCompleted}
                    disabled={busy}
                    onChange={(e) => {
                      setOnlyCompleted(e.target.checked);
                      clearTasks();
                    }}
                  />
                  Nur erledigte / geschlossene Aufgaben
                </label>
              </div>
              <p className="tl-hint">
                Abgeschlossene Aufgaben und Unteraufgaben werden mitgeladen. Du
                kannst Aufgaben aus mehreren Listen desselben ClickUp-Workspaces
                auswählen; maximal 20 pro Import.
              </p>
              <button
                className="button"
                disabled={busy || !list}
                onClick={() => void preview()}
              >
                Aufgaben laden
              </button>
              {searched && (
                <>
                  <div className="tl-jira-table-wrap">
                    <table className="tl-jira-table">
                      <thead>
                        <tr>
                          <th>Auswahl</th>
                          <th>Aufgabe</th>
                          <th>Liste / Status</th>
                          <th>Gebuchte Zeit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tasks.map((t) => (
                          <tr key={t.id}>
                            <td>
                              <input
                                type="checkbox"
                                aria-label={`${t.id} auswählen`}
                                checked={selection.some((s) => s.id === t.id)}
                                disabled={
                                  busy ||
                                  (!selection.some((s) => s.id === t.id) &&
                                    selection.length >= 20)
                                }
                                onChange={() => toggle(t)}
                              />
                            </td>
                            <td>
                              <strong>{t.title}</strong>
                              <small>
                                {t.id}
                                {t.parent_id
                                  ? ` · Unteraufgabe von ${t.parent_id}`
                                  : ""}
                              </small>
                              {t.imported && (
                                <span className="tl-base-label">
                                  Ticket vorhanden · fehlende Zeiten ergänzbar
                                </span>
                              )}
                            </td>
                            <td>
                              {t.list_name}
                              <span>{t.status}</span>
                            </td>
                            <td>{formatMinutes(t.minutes)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!tasks.length && (
                    <p className="tl-hint">
                      Keine passenden Aufgaben auf dieser Seite.
                      {next !== null
                        ? " Weitere Aufgaben sind auf der nächsten Seite verfügbar."
                        : ""}
                    </p>
                  )}
                  {next !== null && (
                    <button
                      className="tl-secondary"
                      disabled={busy}
                      onClick={() => void preview(true)}
                    >
                      Weitere Aufgaben laden
                    </button>
                  )}
                </>
              )}
            </section>
          )}
          {!!selection.length && (
            <section className="tl-workspace-panel">
              <div className="tl-panel-head">
                <h2>3. Gesamte Zeithistorie prüfen</h2>
                <strong>{selection.length} / 20 Aufgaben</strong>
              </div>
              <div className="tl-clickup-selection">
                {selection.map((t) => (
                  <button
                    className="tl-secondary"
                    key={t.id}
                    disabled={busy}
                    aria-label={`${t.title} aus Auswahl entfernen`}
                    onClick={() => toggle(t)}
                  >
                    {t.title} ×
                  </button>
                ))}
              </div>
              <p className="tl-hint">
                Die Prüfung lädt die Einzelbuchungen aus allen Jahren und
                vergleicht ihre Summe mit ClickUp. Fehlende Berechtigungen,
                laufende Timer oder abweichende Summen stoppen den Import. Es
                wird noch kein lokales Ticket angelegt.
              </p>
              <button
                className="button"
                disabled={busy}
                onClick={() => void prepare()}
              >
                {busy
                  ? "Bitte warten …"
                  : "Tickets & gesamte Zeithistorie prüfen"}
              </button>
            </section>
          )}
          {plan && (
            <section className="tl-workspace-panel">
              <h2>4. Geprüfte Historie übernehmen</h2>
              <div className="tl-clickup-summary">
                <div>
                  <strong>{plan.task_count}</strong>
                  <span>Aufgaben</span>
                </div>
                <div>
                  <strong>{plan.entry_count}</strong>
                  <span>Zeitbuchungen</span>
                </div>
                <div>
                  <strong>{formatMinutes(plan.total_minutes)}</strong>
                  <span>Gesamte Quellzeit</span>
                </div>
              </div>
              {plan.date_from && plan.date_to && (
                <p>
                  Historie vom {displayDate(plan.date_from)} bis{" "}
                  {displayDate(plan.date_to)} · Zeitzone {plan.timezone}
                </p>
              )}
              <div className="tl-jira-table-wrap">
                <table className="tl-jira-table">
                  <thead>
                    <tr>
                      <th>Ursprüngliche ClickUp-Person</th>
                      <th>Buchungen</th>
                      <th>Arbeitszeit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.people.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <strong>{p.name}</strong>
                          <small>{p.email || `ClickUp-ID ${p.id}`}</small>
                        </td>
                        <td>{p.entry_count}</td>
                        <td>{formatMinutes(p.minutes)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="tl-hint">
                Passende aktive Projektmitglieder werden anhand ihrer E-Mail
                zugeordnet. Andere Personen bleiben als historische
                ClickUp-Mitwirkende erhalten und erhalten kein Konto oder
                Projektzugriff. Dauern bleiben exakt, einschließlich Sekunden;
                das Buchungsdatum folgt der Startzeit. Importierte Zeiten sind
                als Quellhistorie nur lesbar.
              </p>
              <p className="tl-hint">
                Prüfstand {new Date(plan.prepared_at).toLocaleString("de-DE")} ·
                30 Minuten gültig. Bereits vorhandene Tickets und Zeitbuchungen
                werden nicht doppelt angelegt.
              </p>
              {plan.warnings.map((w, i) => (
                <p key={i} className="tl-hint">
                  {w}
                </p>
              ))}
              <button
                className="button"
                disabled={busy}
                onClick={() => void commit()}
              >
                Tickets und Zeiten nach {current.name} importieren
              </button>
            </section>
          )}
          {result && (
            <section className="tl-workspace-panel" role="status">
              <h2>Import abgeschlossen</h2>
              <p>
                {result.created.length} neue Tickets · {result.skipped.length}{" "}
                Tickets bereits vorhanden · {result.projects_created.length}{" "}
                Projekte angelegt
              </p>
              <p>
                <strong>
                  {result.time_entries_created} Zeitbuchungen übernommen ·{" "}
                  {formatMinutes(result.imported_minutes)}
                </strong>{" "}
                · {result.time_entries_skipped} Buchungen bereits vorhanden
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
                  <h3>Hinweise</h3>
                  <ul>
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </>
              )}
              <div className="tl-import-actions">
                <Link
                  href={`/dashboard/time?${reportQuery}`}
                  className="button"
                >
                  Importierte Zeithistorie im Bericht öffnen
                </Link>
                <Link
                  href={`/dashboard/projects?workspace=${workspace}`}
                  className="tl-secondary"
                >
                  Projekte öffnen
                </Link>
              </div>
              <p className="tl-hint">
                Die Übernahme kopiert die ausgewählte Historie. Die
                ursprünglichen Aufgaben und Zeiten in ClickUp bleiben erhalten.
              </p>
            </section>
          )}
        </>
      )}
    </div>
  );
}
