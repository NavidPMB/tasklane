"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  type Workspace,
  type Person,
  type Project,
  workFetch,
  workAction,
} from "@/lib/work";
import { ProjectForm } from "./project-form";

type Details = { workspace: Workspace; members: Person[] };
export function WorkspaceManager({
  initialWorkspace,
}: {
  initialWorkspace?: number;
}) {
  const [spaces, setSpaces] = useState<Workspace[]>([]),
    [selected, setSelected] = useState(initialWorkspace || 0);
  const [details, setDetails] = useState<Details | null>(null),
    [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [newProject, setNewProject] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const result = await workFetch<{ workspaces: Workspace[] }>(
      "/api/work/workspaces/",
      signal,
    );
    if (signal?.aborted) return;
    setSpaces(result.workspaces);
    setSelected((current) =>
      result.workspaces.some((w) => w.id === current)
        ? current
        : result.workspaces[0]?.id || 0,
    );
  }, []);
  const refresh = useCallback(async () => {
    if (!selected) return;
    const [data, result] = await Promise.all([
      workAction<Details>("get_workspace", { workspace_id: selected }),
      workFetch<{ projects: Project[] }>(
        `/api/work/projects/?workspace_id=${selected}`,
      ),
    ]);
    return { data, projects: result.projects };
  }, [selected]);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((err) => {
      if (err.name !== "AbortError") setError(err.message);
    });
    return () => controller.abort();
  }, [load]);
  useEffect(() => {
    let active = true;
    setDetails(null);
    setProjects([]);
    setError("");
    setNotice("");
    refresh()
      .then((r) => {
        if (active && r) {
          setDetails(r.data);
          setProjects(r.projects);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  async function run(
    action: string,
    args: Record<string, unknown>,
    form?: HTMLFormElement,
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await workAction<Workspace>(action, args);
      form?.reset();
      if (action === "create_workspace") {
        await load();
        setSelected(result.id);
      } else {
        const r = await refresh();
        if (r) {
          setDetails(r.data);
          setProjects(r.projects);
        }
        await load();
      }
      setNotice("Gespeichert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Änderung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  function submit(
    event: FormEvent<HTMLFormElement>,
    action: string,
    args: Record<string, unknown> = {},
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    void run(
      action,
      { ...Object.fromEntries(new FormData(form)), ...args },
      form,
    );
  }
  return (
    <div className="tasklane-app">
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">GEMEINSAM ARBEITEN</p>
          <h1>Workspaces & Team</h1>
          <p>
            Ein Workspace verbindet dein Team mit allen zugehörigen Projekten.
          </p>
        </div>
      </div>
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
      <div className="tl-workspace-layout">
        <aside className="tl-workspace-panel">
          <h2>Deine Workspaces</h2>
          <div className="tl-space-list">
            {spaces.map((w) => (
              <button
                key={w.id}
                className={selected === w.id ? "active" : ""}
                disabled={busy}
                onClick={() => {
                  setSelected(w.id);
                  window.history.replaceState(null, "", `?workspace=${w.id}`);
                }}
              >
                {w.name}
                <small>
                  {w.project_count} Projekte ·{" "}
                  {w.can_manage ? "Leitung" : "Mitglied / Projektgast"}
                </small>
              </button>
            ))}
          </div>
          <form
            className="tl-form"
            onSubmit={(e) => submit(e, "create_workspace")}
          >
            <h3>Workspace erstellen</h3>
            <label>
              Name
              <input
                name="name"
                required
                maxLength={120}
                placeholder="Zum Beispiel: GroupFractal"
              />
            </label>
            <button className="button" disabled={busy}>
              Workspace erstellen
            </button>
          </form>
        </aside>
        <div>
          {details ? (
            <>
              <section className="tl-workspace-panel">
                <div className="tl-panel-head">
                  <h2>{details.workspace.name}</h2>
                  <Link
                    href={`/dashboard?workspace=${selected}`}
                    className="tl-secondary"
                  >
                    Zum Board
                  </Link>
                </div>
                {details.workspace.can_manage && (
                  <form
                    key={`${selected}-${details.workspace.name}`}
                    className="tl-inline-form"
                    onSubmit={(e) =>
                      submit(e, "update_workspace", { workspace_id: selected })
                    }
                  >
                    <label className="sr-only" htmlFor="workspace-name">
                      Workspace-Name ändern
                    </label>
                    <input
                      id="workspace-name"
                      name="name"
                      defaultValue={details.workspace.name}
                      required
                      maxLength={120}
                    />
                    <button className="tl-secondary" disabled={busy}>
                      Umbenennen
                    </button>
                  </form>
                )}
                <h3>Workspace-Team</h3>
                <p className="tl-hint">
                  Mitglieder sehen alle bestehenden und zukünftigen Projekte
                  dieses Workspaces. Eine Freigabe gilt für alle aktuellen und
                  künftigen Projekte.
                </p>
                <div className="tl-members">
                  {details.members.map((member) => (
                    <div className="tl-member" key={member.id}>
                      <span className="tl-avatar">
                        {member.name[0].toUpperCase()}
                      </span>
                      <div>
                        <strong>{member.name}</strong>
                        <small>{member.email}</small>
                      </div>
                      {member.id === details.workspace.owner_id ? (
                        <span className="tl-base-label">Workspace-Leitung</span>
                      ) : (
                        details.workspace.can_manage && (
                          <button
                            className="tl-plain-button tl-danger"
                            disabled={busy}
                            onClick={() => {
                              if (
                                window.confirm(
                                  `${member.name} aus dem Workspace entfernen? Separate Projektfreigaben bleiben erhalten.`,
                                )
                              )
                                void run("remove_workspace_member", {
                                  workspace_id: selected,
                                  user_id: member.id,
                                });
                            }}
                          >
                            Entfernen
                          </button>
                        )
                      )}
                    </div>
                  ))}
                </div>
                {details.workspace.can_manage && (
                  <form
                    className="tl-form tl-inline-panel"
                    onSubmit={(e) =>
                      submit(e, "add_workspace_member", {
                        workspace_id: selected,
                      })
                    }
                  >
                    <h3>Workspace teilen</h3>
                    <label>
                      E-Mail des Teammitglieds
                      <input
                        type="email"
                        name="email"
                        required
                        maxLength={254}
                        placeholder="sina@dein-team.de"
                      />
                    </label>
                    <p className="tl-hint">
                      Die Person benötigt ein aktives Tasklane-Konto. Ein
                      Administrator kann es unter Benutzer anlegen. Es wird
                      keine Einladung per E-Mail versendet.
                    </p>
                    <button className="button" disabled={busy}>
                      Mitglied hinzufügen
                    </button>
                  </form>
                )}
              </section>
              <section className="tl-workspace-panel">
                <div className="tl-panel-head">
                  <h2>Projekte ({projects.length})</h2>
                  {details.workspace.can_create_project && (
                    <button
                      className="tl-secondary"
                      onClick={() => setNewProject(true)}
                    >
                      Projekt erstellen
                    </button>
                  )}
                </div>
                <div className="tl-space-projects">
                  {projects.map((p) => (
                    <Link
                      key={p.id}
                      href={`/dashboard?workspace=${selected}&project=${p.id}`}
                    >
                      <strong>
                        {p.key} · {p.name}
                      </strong>
                      <span>{p.ticket_count} Tickets →</span>
                    </Link>
                  ))}
                </div>
                {!projects.length && (
                  <p className="tl-hint">
                    Noch keine Projekte. Erstelle das erste Projekt oder
                    importiere Tickets aus Jira.
                  </p>
                )}
                {details.workspace.can_manage && (
                  <>
                    <Link
                      className="button"
                      href={`/dashboard/jira?workspace=${selected}`}
                    >
                      Jira verbinden & Tickets importieren
                    </Link>
                    <Link
                      className="tl-secondary"
                      href={`/dashboard/clickup?workspace=${selected}`}
                    >
                      ClickUp mit Zeithistorie importieren
                    </Link>
                  </>
                )}
              </section>
            </>
          ) : (
            <div className="tl-workspace-panel">
              <h2>Platz für dein Team</h2>
              <p>
                Erstelle einen Workspace, teile ihn mit deinem Team und
                organisiere darin deine Projekte.
              </p>
            </div>
          )}
        </div>
      </div>
      {newProject && (
        <ProjectForm
          workspaces={spaces}
          workspaceId={selected}
          onClose={() => setNewProject(false)}
          onSaved={async () => {
            const r = await refresh();
            if (r) {
              setDetails(r.data);
              setProjects(r.projects);
            }
            await load();
          }}
        />
      )}
    </div>
  );
}
