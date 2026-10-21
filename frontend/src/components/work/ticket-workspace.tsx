"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/icon";
import {
  type Project,
  type Workspace,
  type ProjectData,
  type Ticket,
  priorities,
  workAction,
  workFetch,
  WorkRequestError,
} from "@/lib/work";
import { ProjectForm } from "./project-form";
import { TicketForm } from "./ticket-form";
import { WorkflowSettings } from "./workflow-settings";
import { formatMinutes } from "@/lib/time";

type Editor = {
  ticket?: Ticket;
  parentId?: number;
  initialStatus?: number;
  initialKind?: "epic" | "ticket";
};
export function TicketWorkspace({
  userId,
  initialView = "board",
  initialProject,
  initialWorkspace,
}: {
  userId: number;
  initialView?: string;
  initialProject?: number;
  initialWorkspace?: number;
}) {
  const [allProjects, setProjects] = useState<Project[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState(initialWorkspace || 0);
  const workspaceRef = useRef(workspace);
  workspaceRef.current = workspace;
  const projects = allProjects.filter(
    (p) => !workspace || p.workspace_id === workspace,
  );
  const [selected, setSelected] = useState<number | null>(
    initialProject || null,
  );
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const [data, setData] = useState<ProjectData | null>(null);
  const [view, setView] = useState(initialView);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [newProject, setNewProject] = useState(false);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [settings, setSettings] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [epicFilter, setEpicFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [dragOver, setDragOver] = useState<number | null>(null);

  const loadProjects = useCallback(async (signal?: AbortSignal) => {
    const [result, spaces] = await Promise.all([
      workFetch<{ projects: Project[] }>("/api/work/projects/", signal),
      workFetch<{ workspaces: Workspace[] }>("/api/work/workspaces/", signal),
    ]);
    setWorkspaces(spaces.workspaces);
    if (
      workspaceRef.current &&
      !spaces.workspaces.some((w) => w.id === workspaceRef.current)
    ) {
      workspaceRef.current = 0;
      setWorkspace(0);
    }
    const visible = result.projects.filter(
      (p) => !workspaceRef.current || p.workspace_id === workspaceRef.current,
    );
    setProjects(result.projects);
    setSelected((current) =>
      visible.some((p) => p.id === current) ? current : visible[0]?.id || null,
    );
    return result.projects;
  }, []);
  const refresh = useCallback(async () => {
    if (!selected) return;
    try {
      const result = await workFetch<ProjectData>(
        `/api/work/projects/${selected}/`,
      );
      if (selectedRef.current === selected) setData(result);
    } catch (err) {
      if (err instanceof WorkRequestError && [403, 404].includes(err.status)) {
        if (selectedRef.current === selected) setData(null);
        await loadProjects();
      }
      throw err;
    }
  }, [selected, loadProjects]);
  const afterSaved = useCallback(async () => {
    await refresh();
    await loadProjects();
    setNotice("Gespeichert.");
  }, [refresh, loadProjects]);

  useEffect(() => {
    const controller = new AbortController();
    loadProjects(controller.signal)
      .then(() => setError(""))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadProjects]);
  useEffect(() => {
    setData(null);
    setEditor(null);
    setSettings(false);
    setSearch("");
    setStatusFilter("");
    setAssigneeFilter("");
    setTagFilter("");
    setEpicFilter("");
    setKindFilter("");
    setError("");
    if (!selected) return;
    const controller = new AbortController();
    setLoading(true);
    workFetch<ProjectData>(`/api/work/projects/${selected}/`, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selected]);
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      if (document.hidden) return;
      try {
        await loadProjects();
        await refresh();
        if (mounted) setError("");
      } catch (err) {
        if (mounted)
          setError(
            err instanceof Error
              ? err.message
              : "Aktualisierung fehlgeschlagen.",
          );
      }
    };
    const interval = window.setInterval(poll, 10000);
    window.addEventListener("focus", poll);
    return () => {
      mounted = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", poll);
    };
  }, [refresh, loadProjects]);
  useEffect(() => {
    if (!data) return;
    if (
      statusFilter &&
      !data.statuses.some((s) => s.id === Number(statusFilter))
    )
      setStatusFilter("");
    if (tagFilter && !data.tags.some((t) => t.id === Number(tagFilter)))
      setTagFilter("");
    if (
      assigneeFilter &&
      !data.members.some((u) => u.id === Number(assigneeFilter))
    )
      setAssigneeFilter("");
    if (
      epicFilter &&
      !data.tickets.some(
        (t) => t.id === Number(epicFilter) && t.kind === "epic",
      )
    )
      setEpicFilter("");
  }, [data, statusFilter, tagFilter, assigneeFilter, epicFilter]);
  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(""), 3500);
    return () => clearTimeout(timeout);
  }, [notice]);

  function selectProject(projectId: number, workspaceId?: number) {
    setSelected(projectId);
    const target = allProjects.find((p) => p.id === projectId);
    if (workspaceId || target) {
      const id = workspaceId || target!.workspace_id;
      workspaceRef.current = id;
      setWorkspace(id);
    }
    setView("board");
    window.history.replaceState(
      null,
      "",
      `/dashboard?project=${projectId}&workspace=${workspaceId || allProjects.find((p) => p.id === projectId)?.workspace_id || workspace}`,
    );
  }
  async function changeStatus(ticket: Ticket, statusId: number) {
    if (busy || ticket.status_id === statusId) return;
    setBusy(true);
    setError("");
    try {
      await workAction("update_ticket", {
        project_id: ticket.project_id,
        ticket_id: ticket.id,
        status_id: statusId,
        expected_updated_at: ticket.updated_at,
      });
      await refresh();
      setNotice(`${ticket.key} verschoben.`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Verschieben fehlgeschlagen.",
      );
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  const lookup = new Map(data?.tickets.map((t) => [t.id, t]));
  const descendantOf = (ticket: Ticket, id: number) => {
    const visited = new Set<number>();
    let node: Ticket | undefined = ticket;
    while (node && !visited.has(node.id)) {
      if (node.id === id) return true;
      visited.add(node.id);
      node = node.parent_id ? lookup.get(node.parent_id) : undefined;
    }
    return false;
  };
  const tickets = (data?.tickets || []).filter((t) => {
    const haystack = `${t.key} ${t.title} ${t.description}`.toLocaleLowerCase(
      "de",
    );
    return (
      (!search || haystack.includes(search.toLocaleLowerCase("de"))) &&
      (!statusFilter || t.status_id === Number(statusFilter)) &&
      (!assigneeFilter || t.assignee_ids.includes(Number(assigneeFilter))) &&
      (!tagFilter || t.tag_ids.includes(Number(tagFilter))) &&
      (!epicFilter || descendantOf(t, Number(epicFilter))) &&
      (!kindFilter || t.kind === kindFilter)
    );
  });
  const visibleIds = new Set(tickets.map((t) => t.id));
  const tree: { ticket: Ticket; depth: number }[] = [];
  const visit = (ticket: Ticket, depth: number) => {
    tree.push({ ticket, depth });
    tickets
      .filter((t) => t.parent_id === ticket.id)
      .forEach((t) => visit(t, depth + 1));
  };
  tickets
    .filter((t) => !t.parent_id || !visibleIds.has(t.parent_id))
    .sort((a, b) => Number(b.kind === "epic") - Number(a.kind === "epic"))
    .forEach((t) => visit(t, 0));
  const completed =
    data?.tickets.filter((t) =>
      ["done", "closed"].includes(
        data.statuses.find((s) => s.id === t.status_id)?.category || "",
      ),
    ).length || 0;
  const inProgress =
    data?.tickets.filter(
      (t) =>
        data.statuses.find((s) => s.id === t.status_id)?.category ===
        "in_progress",
    ).length || 0;
  const hasFilters = !!(
    search ||
    statusFilter ||
    assigneeFilter ||
    tagFilter ||
    epicFilter ||
    kindFilter
  );
  function clearFilters() {
    setSearch("");
    setStatusFilter("");
    setAssigneeFilter("");
    setTagFilter("");
    setEpicFilter("");
    setKindFilter("");
  }

  function ticketMeta(ticket: Ticket) {
    return (
      <>
        <div className="tl-ticket-labels">
          {ticket.logged_minutes > 0 && (
            <span className="tl-time-badge" title="Gebuchte Arbeitszeit">
              <Icon name="clock" width={11} height={11} />
              {formatMinutes(ticket.logged_minutes)}
            </span>
          )}
          <span className={`tl-kind tl-kind-${ticket.kind}`}>
            {ticket.kind === "epic"
              ? "Epic"
              : ticket.parent_id
                ? "Unterticket"
                : "Ticket"}
          </span>
          <span className={`tl-priority tl-priority-${ticket.priority}`}>
            {priorities[ticket.priority]}
          </span>
          {ticket.tag_ids.map((id) => (
            <span className="tl-tag" key={id}>
              #{data?.tags.find((t) => t.id === id)?.name}
            </span>
          ))}
        </div>
        <div className="tl-ticket-bottom">
          <div className="tl-avatar-stack">
            {ticket.assignee_ids.length ? (
              ticket.assignee_ids.map((id) => {
                const member = data?.members.find((u) => u.id === id);
                return (
                  <span
                    className="tl-mini-avatar"
                    key={id}
                    title={member?.name}
                    aria-label={member?.name}
                  >
                    {member?.name.charAt(0).toUpperCase()}
                  </span>
                );
              })
            ) : (
              <span className="tl-unassigned">Nicht zugewiesen</span>
            )}
          </div>
          {ticket.due_date && (
            <time
              className={`tl-due ${ticket.due_date < new Date().toLocaleDateString("sv-SE") && !["done", "closed"].includes(data?.statuses.find((s) => s.id === ticket.status_id)?.category || "") ? "overdue" : ""}`}
              dateTime={ticket.due_date}
            >
              {new Date(`${ticket.due_date}T12:00:00`).toLocaleDateString(
                "de-DE",
                { day: "2-digit", month: "short" },
              )}
            </time>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="tasklane-app">
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">TASKLANE · DEIN TEAM, DEIN FLOW</p>
          <h1>
            {view === "projects"
              ? "Deine Projekte"
              : data?.project.name || "Dein Arbeitsbereich"}
          </h1>
          <p>
            {view === "projects"
              ? "Ein gemeinsamer Platz für jedes Vorhaben."
              : data?.project.description ||
                "Von der ersten Idee bis zum erledigten Ticket."}
          </p>
        </div>
        <div className="tl-heading-actions">
          <Link className="tl-secondary" href="/dashboard/mcp">
            <Icon name="terminal" width={16} height={16} />
            MCP verbinden
          </Link>
          <button className="button" onClick={() => setNewProject(true)}>
            <Icon name="plus" width={16} height={16} />
            Projekt erstellen
          </button>
        </div>
      </div>
      <div className="tl-workspace-bar">
        <label>
          Workspace{" "}
          <select
            aria-label="Workspace auswählen"
            value={workspace}
            onChange={(e) => {
              const id = Number(e.target.value);
              setWorkspace(id);
              workspaceRef.current = id;
              setSelected(
                allProjects.find((p) => !id || p.workspace_id === id)?.id ||
                  null,
              );
              window.history.replaceState(
                null,
                "",
                `/dashboard${view === "projects" ? "/projects" : ""}${id ? `?workspace=${id}` : ""}`,
              );
            }}
          >
            <option value={0}>Alle Workspaces</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.project_count})
              </option>
            ))}
          </select>
        </label>
        <Link
          className="tl-secondary"
          href={`/dashboard/workspaces${workspace ? `?workspace=${workspace}` : ""}`}
        >
          Workspace & Team
        </Link>
        <Link
          className="tl-secondary"
          href={`/dashboard/jira${workspace ? `?workspace=${workspace}` : ""}`}
        >
          Aus Jira importieren
        </Link>
        <Link
          className="tl-secondary"
          href={`/dashboard/clickup${workspace ? `?workspace=${workspace}` : ""}`}
        >
          Aus ClickUp importieren
        </Link>
      </div>
      {error && (
        <div className="tl-error" role="alert">
          {error}
          <button
            className="tl-plain-button"
            onClick={() => {
              void loadProjects()
                .then(refresh)
                .catch((err) => setError(err.message));
            }}
          >
            Erneut laden
          </button>
        </div>
      )}
      <div role="status" className={`tl-toast ${notice ? "is-visible" : ""}`}>
        {notice}
      </div>
      {view === "projects" ? (
        <div className="tl-project-grid">
          {projects.map((p) => (
            <button
              key={p.id}
              className="tl-project-card"
              onClick={() => selectProject(p.id)}
            >
              <span className="tl-project-mark">{p.key.slice(0, 2)}</span>
              <span className="tl-project-card-key">
                {p.workspace_name} · {p.key}
              </span>
              <h2>{p.name}</h2>
              <p>{p.description || "Bereit für die nächsten Schritte."}</p>
              <div>
                <span>{p.ticket_count} Tickets</span>
                <span>{p.can_manage ? "Projektleitung" : "Mitglied"}</span>
                <Icon name="arrow" width={16} height={16} />
              </div>
            </button>
          ))}
          <button
            className="tl-project-add"
            onClick={() => setNewProject(true)}
          >
            <Icon name="plus" width={26} height={26} />
            <strong>Neues Projekt</strong>
            <span>Ideen einen Platz geben</span>
          </button>
        </div>
      ) : (
        projects.length > 0 && (
          <>
            <div className="tl-project-toolbar">
              <label className="tl-project-picker">
                <span className="sr-only">Projekt auswählen</span>
                <Icon name="layers" width={18} height={18} />
                <select
                  value={selected || ""}
                  onChange={(e) => selectProject(Number(e.target.value))}
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.key} · {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="tl-toolbar-right">
                {data && (
                  <>
                    <div className="tl-avatar-stack tl-team-avatars">
                      {data.members.slice(0, 5).map((u) => (
                        <span
                          className="tl-mini-avatar"
                          key={u.id}
                          title={u.name}
                        >
                          {u.name.charAt(0).toUpperCase()}
                        </span>
                      ))}
                      <span className="tl-hint">
                        {data.members.length} im Team
                      </span>
                    </div>
                    <button
                      className="tl-secondary"
                      onClick={() => setSettings(true)}
                    >
                      <Icon name="settings" width={16} height={16} />
                      Workflow & Team
                    </button>
                    <Link
                      className="tl-secondary"
                      href={`/dashboard/time?project=${data.project.id}`}
                    >
                      <Icon name="clock" width={16} height={16} />
                      Zeiten & Berichte
                    </Link>
                  </>
                )}
              </div>
            </div>
            {data && (
              <>
                <div className="tl-stats">
                  <div>
                    <span className="tl-stat-value">{data.tickets.length}</span>
                    <span>Tickets gesamt</span>
                  </div>
                  <div>
                    <span className="tl-stat-value">{inProgress}</span>
                    <span>In Arbeit</span>
                  </div>
                  <div>
                    <span className="tl-stat-value">{completed}</span>
                    <span>Abgeschlossen</span>
                  </div>
                  <div className="tl-progress-stat">
                    <span className="tl-stat-value">
                      {data.tickets.length
                        ? Math.round((completed / data.tickets.length) * 100)
                        : 0}
                      %
                    </span>
                    <span>Fortschritt</span>
                    <progress
                      max={data.tickets.length || 1}
                      value={completed}
                      aria-label="Projektfortschritt"
                    />
                  </div>
                </div>
                <div className="tl-view-toolbar">
                  <div className="tl-tabs">
                    <button
                      className={view === "board" ? "active" : ""}
                      onClick={() => setView("board")}
                    >
                      <Icon name="board" width={16} height={16} />
                      Board
                    </button>
                    <button
                      className={view === "list" ? "active" : ""}
                      onClick={() => setView("list")}
                    >
                      <Icon name="menu" width={16} height={16} />
                      Liste & Hierarchie
                    </button>
                  </div>
                  <div className="tl-toolbar-right">
                    <button
                      className="tl-secondary"
                      onClick={() => setEditor({ initialKind: "epic" })}
                    >
                      <Icon name="layers" width={15} height={15} />
                      Epic
                    </button>
                    <button
                      className="button button-small"
                      onClick={() => setEditor({})}
                    >
                      <Icon name="plus" width={15} height={15} />
                      Ticket erstellen
                    </button>
                  </div>
                </div>
                <div className="tl-filters">
                  <label className="tl-search">
                    <Icon name="search" width={17} height={17} />
                    <input
                      aria-label="Tickets durchsuchen"
                      placeholder="Tickets durchsuchen …"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                  <select
                    aria-label="Status filtern"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="">Alle Status</option>
                    {data.categories.map((c) => (
                      <optgroup label={c.name} key={c.id}>
                        {data.statuses
                          .filter((s) => s.category === c.id)
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                      </optgroup>
                    ))}
                  </select>
                  <select
                    aria-label="Zuweisung filtern"
                    value={assigneeFilter}
                    onChange={(e) => setAssigneeFilter(e.target.value)}
                  >
                    <option value="">Alle Zuständigen</option>
                    {data.members.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Tag filtern"
                    value={tagFilter}
                    onChange={(e) => setTagFilter(e.target.value)}
                  >
                    <option value="">Alle Tags</option>
                    {data.tags.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Epic filtern"
                    value={epicFilter}
                    onChange={(e) => setEpicFilter(e.target.value)}
                  >
                    <option value="">Alle Epics</option>
                    {data.tickets
                      .filter((t) => t.kind === "epic")
                      .map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.title}
                        </option>
                      ))}
                  </select>
                  <select
                    aria-label="Tickettyp filtern"
                    value={kindFilter}
                    onChange={(e) => setKindFilter(e.target.value)}
                  >
                    <option value="">Alle Typen</option>
                    <option value="epic">Epics</option>
                    <option value="ticket">Tickets</option>
                  </select>
                  <button
                    className={`tl-filter-button ${assigneeFilter === String(userId) ? "active" : ""}`}
                    onClick={() =>
                      setAssigneeFilter(
                        assigneeFilter === String(userId) ? "" : String(userId),
                      )
                    }
                  >
                    Meine Tickets
                  </button>
                  {hasFilters && (
                    <button className="tl-plain-button" onClick={clearFilters}>
                      Zurücksetzen
                    </button>
                  )}
                </div>
                <div className="tl-results-meta">
                  <span>
                    {tickets.length}{" "}
                    {hasFilters ? `von ${data.tickets.length} ` : ""}Tickets
                  </span>
                  <span>
                    <span className="tl-live-dot" />
                    Automatisch aktuell · alle 10 Sekunden
                  </span>
                </div>
                {view === "board" ? (
                  <div className="tl-board" aria-label="Ticketboard">
                    {data.statuses.map((status) => (
                      <section
                        key={status.id}
                        className={`tl-column ${dragOver === status.id ? "tl-drag-over" : ""}`}
                        aria-label={`Status ${status.name}`}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragOver(status.id);
                        }}
                        onDragLeave={(e) => {
                          if (
                            !e.currentTarget.contains(e.relatedTarget as Node)
                          )
                            setDragOver(null);
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          setDragOver(null);
                          const ticket = lookup.get(
                            Number(
                              e.dataTransfer.getData(
                                "application/x-tasklane-ticket",
                              ),
                            ),
                          );
                          if (ticket) void changeStatus(ticket, status.id);
                        }}
                      >
                        <div className="tl-column-head">
                          <div>
                            <span
                              className={`tl-dot tl-category-${status.category}`}
                            />
                            <h2>{status.name}</h2>
                            <span className="tl-count">
                              {
                                tickets.filter((t) => t.status_id === status.id)
                                  .length
                              }
                            </span>
                          </div>
                          <button
                            className="tl-plain-button"
                            aria-label={`Ticket in ${status.name} erstellen`}
                            onClick={() =>
                              setEditor({ initialStatus: status.id })
                            }
                          >
                            <Icon name="plus" width={17} height={17} />
                          </button>
                        </div>
                        <span className="tl-column-category">
                          {
                            data.categories.find(
                              (c) => c.id === status.category,
                            )?.name
                          }
                          {status.is_base ? " · Grundstatus" : ""}
                        </span>
                        <div className="tl-column-cards">
                          {tickets
                            .filter((t) => t.status_id === status.id)
                            .map((ticket) => (
                              <article
                                key={ticket.id}
                                className={`tl-ticket-card ${ticket.kind === "epic" ? "tl-epic-card" : ""}`}
                                draggable={!busy}
                                onDragStart={(e) => {
                                  e.dataTransfer.setData(
                                    "application/x-tasklane-ticket",
                                    String(ticket.id),
                                  );
                                  e.dataTransfer.effectAllowed = "move";
                                }}
                                onDragEnd={() => setDragOver(null)}
                              >
                                <div className="tl-card-top">
                                  <span>{ticket.key}</span>
                                  <button
                                    className="tl-plain-button"
                                    title="Unterticket erstellen"
                                    aria-label={`Unterticket für ${ticket.key} erstellen`}
                                    onClick={() =>
                                      setEditor({ parentId: ticket.id })
                                    }
                                  >
                                    <Icon name="plus" width={14} height={14} />
                                  </button>
                                </div>
                                <button
                                  className="tl-ticket-title"
                                  onClick={() => setEditor({ ticket })}
                                >
                                  {ticket.title}
                                </button>
                                {ticket.parent_id && (
                                  <button
                                    className="tl-parent-link"
                                    onClick={() => {
                                      const parent = lookup.get(
                                        ticket.parent_id!,
                                      );
                                      if (parent) setEditor({ ticket: parent });
                                    }}
                                  >
                                    <Icon
                                      name="layers"
                                      width={12}
                                      height={12}
                                    />
                                    {lookup.get(ticket.parent_id)?.key} ·{" "}
                                    {lookup.get(ticket.parent_id)?.title}
                                  </button>
                                )}
                                {ticketMeta(ticket)}
                                <select
                                  className="tl-card-status"
                                  aria-label={`Status für ${ticket.key}`}
                                  value={ticket.status_id}
                                  disabled={busy}
                                  onChange={(e) =>
                                    changeStatus(ticket, Number(e.target.value))
                                  }
                                >
                                  {data.categories.map((c) => (
                                    <optgroup label={c.name} key={c.id}>
                                      {data.statuses
                                        .filter((s) => s.category === c.id)
                                        .map((s) => (
                                          <option key={s.id} value={s.id}>
                                            {s.name}
                                          </option>
                                        ))}
                                    </optgroup>
                                  ))}
                                </select>
                              </article>
                            ))}
                          {!tickets.some((t) => t.status_id === status.id) && (
                            <div className="tl-column-empty">
                              {hasFilters
                                ? "Keine passenden Tickets"
                                : "Noch keine Tickets"}
                            </div>
                          )}
                        </div>
                        <button
                          className="tl-column-add"
                          onClick={() =>
                            setEditor({ initialStatus: status.id })
                          }
                        >
                          <Icon name="plus" width={14} height={14} />
                          Ticket hinzufügen
                        </button>
                      </section>
                    ))}
                  </div>
                ) : (
                  <div className="tl-table-wrap">
                    <table className="tl-ticket-table">
                      <thead>
                        <tr>
                          <th>Ticket & Hierarchie</th>
                          <th>Status</th>
                          <th>Zuweisung & Tags</th>
                          <th>Aktion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tree.map(({ ticket, depth }) => (
                          <tr key={ticket.id}>
                            <td>
                              <div
                                style={{ paddingLeft: Math.min(depth, 8) * 20 }}
                                className="tl-tree-cell"
                              >
                                <span className="tl-tree-branch">
                                  {depth
                                    ? "↳"
                                    : ticket.kind === "epic"
                                      ? "◇"
                                      : "·"}
                                </span>
                                <div>
                                  <span className="tl-table-key">
                                    {ticket.key} ·{" "}
                                    {ticket.kind === "epic" ? "Epic" : "Ticket"}
                                  </span>
                                  <button
                                    className="tl-ticket-title"
                                    onClick={() => setEditor({ ticket })}
                                  >
                                    {ticket.title}
                                  </button>
                                </div>
                              </div>
                            </td>
                            <td>
                              <select
                                aria-label={`Status für ${ticket.key}`}
                                value={ticket.status_id}
                                disabled={busy}
                                onChange={(e) =>
                                  changeStatus(ticket, Number(e.target.value))
                                }
                              >
                                {data.statuses.map((s) => (
                                  <option key={s.id} value={s.id}>
                                    {s.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>{ticketMeta(ticket)}</td>
                            <td>
                              <button
                                className="tl-secondary"
                                onClick={() =>
                                  setEditor({ parentId: ticket.id })
                                }
                              >
                                <Icon name="plus" width={14} height={14} />
                                Unterticket
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!tickets.length && (
                      <div className="tl-empty-inline">
                        Keine Tickets gefunden.
                        {hasFilters && (
                          <button
                            className="tl-plain-button"
                            onClick={clearFilters}
                          >
                            Filter zurücksetzen
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )
      )}
      {loading && (
        <div className="tl-loading" role="status">
          Arbeitsbereich wird geladen …
        </div>
      )}
      {!loading && !projects.length && view !== "projects" && !error && (
        <div className="tl-empty">
          <span className="tl-empty-icon">
            <Icon name="board" width={34} height={34} />
          </span>
          <p className="eyebrow">PLATZ FÜR DEIN NÄCHSTES VORHABEN</p>
          <h2>
            Gute Arbeit beginnt mit{" "}
            {workspaces.length ? "einem Projekt" : "einem Workspace"}.
          </h2>
          <p>
            Erstelle dein erstes Projekt. Organisiere Epics, verteile Tickets
            <br />
            und passe den Workflow an dein Team an.
          </p>
          {workspaces.length ? (
            <button className="button" onClick={() => setNewProject(true)}>
              <Icon name="plus" width={16} height={16} />
              Erstes Projekt erstellen
            </button>
          ) : (
            <Link className="button" href="/dashboard/workspaces">
              Ersten Workspace erstellen
            </Link>
          )}
          <div className="tl-empty-features">
            <span>◇ Epics & Untertickets</span>
            <span>▤ Flexible Boards</span>
            <span>⌘ MCP-Anbindung</span>
          </div>
        </div>
      )}
      {newProject && (
        <ProjectForm
          workspaces={workspaces}
          workspaceId={workspace || undefined}
          onClose={() => setNewProject(false)}
          onSaved={async (project) => {
            await loadProjects();
            selectProject(project.id, project.workspace_id);
            setNotice("Projekt erstellt.");
          }}
        />
      )}
      {editor && data && (
        <TicketForm
          data={data}
          {...editor}
          onClose={() => setEditor(null)}
          onSaved={afterSaved}
        />
      )}
      {settings && data && (
        <WorkflowSettings
          data={data}
          onClose={() => setSettings(false)}
          onSaved={afterSaved}
        />
      )}
    </div>
  );
}
