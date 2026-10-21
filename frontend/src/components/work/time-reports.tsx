"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { type Project, type Workspace, workFetch } from "@/lib/work";
import {
  type TimeReport,
  type TimeEntries,
  type TimeEntry,
  localDate,
  displayDate,
  formatMinutes,
} from "@/lib/time";
import { Icon } from "@/components/ui/icon";
import { WorkDialog } from "./dialog";
import { TicketTime, type TimeTicket } from "./ticket-time";

export function TimeReports({
  initialProject,
  initialWorkspace,
  initialFrom,
  initialTo,
}: {
  initialProject?: number;
  initialWorkspace?: number;
  initialFrom?: string;
  initialTo?: string;
}) {
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState(
    initialWorkspace ? String(initialWorkspace) : "",
  );
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState(
    initialProject ? String(initialProject) : "",
  );
  const [person, setPerson] = useState("");
  const [from, setFrom] = useState(() => {
    const now = new Date();
    return (
      initialFrom || localDate(new Date(now.getFullYear(), now.getMonth(), 1))
    );
  });
  const [to, setTo] = useState(initialTo || localDate());
  const [report, setReport] = useState<TimeReport | null>(null),
    [entries, setEntries] = useState<TimeEntries | null>(null);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [view, setView] = useState("team");
  const [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  const [booking, setBooking] = useState<{
    ticket: TimeTicket;
    entry?: TimeEntry;
  } | null>(null);
  const query = new URLSearchParams({ date_from: from, date_to: to });
  if (workspace) query.set("workspace_id", workspace);
  if (project) query.set("project_id", project);
  if (person) query.set("user_id", person);
  const queryString = query.toString();
  const pageSize = 25;
  useEffect(() => {
    if (!from || !to) {
      setReport(null);
      setEntries(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      workFetch<TimeReport>(
        `/api/work/time/report/?${queryString}`,
        controller.signal,
      ),
      workFetch<TimeEntries>(
        `/api/work/time/entries/?${queryString}&offset=${offset}&limit=${pageSize}`,
        controller.signal,
      ),
      workFetch<{ workspaces: Workspace[] }>(
        "/api/work/workspaces/",
        controller.signal,
      ),
      workFetch<{ projects: Project[] }>(
        "/api/work/projects/",
        controller.signal,
      ),
    ])
      .then(([summary, items, workspaces, options]) => {
        if (controller.signal.aborted) return;
        setReport(summary);
        setEntries(items);
        setProjects(options.projects);
        setSpaces(workspaces.workspaces);
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setReport(null);
          setEntries(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [queryString, from, to, offset, revision]);
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden) setRevision((n) => n + 1);
    };
    const interval = setInterval(refresh, 10000);
    window.addEventListener("focus", refresh);
    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", refresh);
    };
  }, []);
  function period(which: string) {
    const now = new Date(),
      start = new Date(now);
    if (which === "month") start.setDate(1);
    if (which === "week")
      start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    setFrom(localDate(start));
    setTo(localDate(now));
    setOffset(0);
  }
  const maxMinutes = Math.max(
    1,
    ...(report?.users.map((u) => u.minutes) || []),
  );
  return (
    <div className="tasklane-app tl-time-reports" aria-busy={loading}>
      <div className="tl-page-heading">
        <div>
          <p className="eyebrow">ZEITERFASSUNG & AUSWERTUNG</p>
          <h1>Wer hat wie viel gearbeitet?</h1>
          <p>
            Gebuchte Arbeitszeit nach Person, Projekt und Ticket – für den
            gewählten Zeitraum.
          </p>
        </div>
        <div className="tl-heading-actions">
          <Link className="tl-secondary" href="/dashboard">
            <Icon name="board" width={16} height={16} />
            Zum Board
          </Link>
          {report && (
            <a
              className="button"
              href={`/api/work/time/export/?${queryString}`}
              download
            >
              <Icon name="arrow" width={16} height={16} />
              CSV exportieren
            </a>
          )}
        </div>
      </div>
      <div className="tl-report-filters">
        <label>
          Workspace
          <select
            aria-label="Workspace"
            value={workspace}
            onChange={(e) => {
              setWorkspace(e.target.value);
              setProject("");
              setPerson("");
              setOffset(0);
            }}
          >
            <option value="">Alle Workspaces</option>
            {spaces.map((w) => (
              <option value={w.id} key={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Projekt
          <select
            value={project}
            aria-label="Projekt"
            onChange={(e) => {
              setProject(e.target.value);
              setPerson("");
              setOffset(0);
            }}
          >
            <option value="">Alle meine Projekte</option>
            {projects
              .filter((p) => !workspace || p.workspace_id === Number(workspace))
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.workspace_name} / {p.key} · {p.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          Person
          <select
            value={person}
            aria-label="Person"
            onChange={(e) => {
              setPerson(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">Alle Personen</option>
            {report?.people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.is_external
                  ? " · ClickUp-Historie"
                  : p.is_active
                    ? ""
                    : " · inaktiv"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Von
          <input
            type="date"
            required
            value={from}
            max={to || undefined}
            onChange={(e) => {
              setFrom(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Bis
          <input
            type="date"
            required
            value={to}
            min={from || undefined}
            onChange={(e) => {
              setTo(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <div className="tl-period-presets">
          <button className="tl-secondary" onClick={() => period("today")}>
            Heute
          </button>
          <button className="tl-secondary" onClick={() => period("week")}>
            Diese Woche
          </button>
          <button className="tl-secondary" onClick={() => period("month")}>
            Dieser Monat
          </button>
        </div>
      </div>
      {error && (
        <p className="tl-error" role="alert">
          {error}
          <button
            className="tl-plain-button"
            onClick={() => setRevision((n) => n + 1)}
          >
            Erneut laden
          </button>
        </p>
      )}
      {!from || !to ? (
        <p className="tl-hint">Bitte einen vollständigen Zeitraum wählen.</p>
      ) : null}
      {loading && !report && (
        <p className="tl-loading" role="status">
          Zeitbericht wird geladen …
        </p>
      )}
      {report && (
        <>
          <div className="tl-stats">
            <div>
              <span className="tl-stat-value" data-testid="time-total">
                {formatMinutes(report.total_minutes)}
              </span>
              <span>Gebuchte Zeit</span>
            </div>
            <div>
              <span className="tl-stat-value">{report.people_count}</span>
              <span>Personen mit Buchungen</span>
            </div>
            <div>
              <span className="tl-stat-value">{report.entry_count}</span>
              <span>Zeitbuchungen</span>
            </div>
            <div>
              <span className="tl-stat-value">{report.ticket_count}</span>
              <span>Tickets</span>
            </div>
          </div>
          <div className="tl-view-toolbar">
            <div className="tl-tabs">
              <button
                className={view === "team" ? "active" : ""}
                onClick={() => setView("team")}
              >
                Teambericht
              </button>
              <button
                className={view === "entries" ? "active" : ""}
                onClick={() => setView("entries")}
              >
                Einzelne Buchungen
              </button>
            </div>
            <span className="tl-hint">
              {displayDate(report.date_from)} – {displayDate(report.date_to)}
            </span>
          </div>
          <p className="tl-hint tl-report-note">
            Zeiten werden der buchenden Person zugerechnet. Eigene Buchungen
            kannst du über das Ticket bearbeiten. Aktualisiert alle 10 Sekunden.
          </p>
          {view === "team" ? (
            <>
              <div className="tl-report-grid">
                <section className="tl-report-panel">
                  <h2>Arbeitszeit pro Person</h2>
                  <div className="tl-table-wrap">
                    <table className="tl-report-table">
                      <thead>
                        <tr>
                          <th>Person</th>
                          <th>Arbeitszeit</th>
                          <th>Buchungen</th>
                          <th>Arbeitstage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...report.users]
                          .sort((a, b) => b.minutes - a.minutes)
                          .map((u) => (
                            <tr key={u.id}>
                              <td>
                                <strong>{u.name}</strong>
                                <small>{u.email}</small>
                              </td>
                              <td>
                                <span>{formatMinutes(u.minutes)}</span>
                                <div
                                  className="tl-hours-bar"
                                  aria-hidden="true"
                                >
                                  <span
                                    style={{
                                      width: `${(u.minutes / maxMinutes) * 100}%`,
                                    }}
                                  />
                                </div>
                              </td>
                              <td>{u.entry_count}</td>
                              <td>{u.day_count}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {!report.users.length && (
                    <p className="tl-empty-inline">
                      Keine Personen im gewählten Bereich.
                    </p>
                  )}
                </section>
                <section className="tl-report-panel">
                  <h2>Arbeitszeit pro Projekt</h2>
                  {report.projects.length ? (
                    <div className="tl-project-times">
                      {report.projects.map((p) => (
                        <div key={p.id}>
                          <div>
                            <strong>{p.name}</strong>
                            <span>{p.key}</span>
                          </div>
                          <strong>{formatMinutes(p.minutes)}</strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="tl-hint">
                      Im gewählten Zeitraum wurde noch keine Arbeitszeit
                      gebucht.
                    </p>
                  )}
                </section>
              </div>
              <section className="tl-report-panel tl-report-tickets">
                <h2>Arbeitszeit pro Ticket</h2>
                <div className="tl-table-wrap">
                  <table className="tl-report-table">
                    <thead>
                      <tr>
                        <th>Ticket</th>
                        <th>Arbeitszeit</th>
                        <th>Aktion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.tickets.map((t) => (
                        <tr key={t.id}>
                          <td>
                            <span className="tl-table-key">{t.key}</span>
                            <strong>{t.title}</strong>
                          </td>
                          <td>{formatMinutes(t.minutes)}</td>
                          <td>
                            <button
                              className="tl-secondary"
                              onClick={() =>
                                setBooking({
                                  ticket: {
                                    id: t.id,
                                    key: t.key,
                                    title: t.title,
                                    project_id: t.project_id,
                                  },
                                })
                              }
                            >
                              <Icon name="clock" width={14} height={14} />
                              Zeit buchen
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!report.tickets.length && (
                  <p className="tl-empty-inline">
                    Öffne ein Ticket im Board und wähle „Zeit erfassen“, um die
                    erste Arbeitszeit zu buchen.
                  </p>
                )}
              </section>
              {report.days.length > 0 && (
                <section className="tl-report-panel tl-report-days">
                  <h2>Arbeitszeit pro Tag</h2>
                  <div className="tl-day-grid">
                    {report.days.map((day) => (
                      <div key={day.date}>
                        <time dateTime={day.date}>{displayDate(day.date)}</time>
                        <strong>{formatMinutes(day.minutes)}</strong>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          ) : (
            <section className="tl-report-panel">
              <h2>Gebuchte Zeiten</h2>
              <div className="tl-table-wrap">
                <table className="tl-report-table tl-entries-table">
                  <thead>
                    <tr>
                      <th>Datum</th>
                      <th>Person</th>
                      <th>Projekt / Ticket</th>
                      <th>Dauer</th>
                      <th>Notiz</th>
                      <th>Aktion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries?.entries.map((entry) => (
                      <tr key={entry.id}>
                        <td>{displayDate(entry.work_date)}</td>
                        <td>{entry.user.name}</td>
                        <td>
                          <span className="tl-table-key">
                            {entry.project_name} · {entry.ticket_key}
                          </span>
                          {entry.ticket_title}
                        </td>
                        <td>{formatMinutes(entry.minutes)}</td>
                        <td className="tl-entry-note">{entry.note || "—"}</td>
                        <td>
                          {entry.can_edit ? (
                            <button
                              className="tl-secondary"
                              onClick={() =>
                                setBooking({
                                  ticket: {
                                    id: entry.ticket_id,
                                    key: entry.ticket_key,
                                    title: entry.ticket_title,
                                    project_id: entry.project_id,
                                  },
                                  entry,
                                })
                              }
                            >
                              Bearbeiten
                            </button>
                          ) : (
                            <span className="tl-hint">
                              {entry.source ? "ClickUp-Historie" : "Nur lesbar"}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {entries?.entries.length === 0 && (
                <p className="tl-empty-inline">
                  Keine Buchungen im gewählten Zeitraum.
                </p>
              )}
              {entries && entries.total > pageSize && (
                <div className="tl-time-pagination">
                  <button
                    className="tl-secondary"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - pageSize))}
                  >
                    Zurück
                  </button>
                  <span>
                    {offset + 1}–{Math.min(offset + pageSize, entries.total)}{" "}
                    von {entries.total}
                  </span>
                  <button
                    className="tl-secondary"
                    disabled={offset + pageSize >= entries.total}
                    onClick={() => setOffset(offset + pageSize)}
                  >
                    Weiter
                  </button>
                </div>
              )}
            </section>
          )}
          {!projects.length && (
            <p className="tl-hint">
              Du hast noch keine Projekte.{" "}
              <Link href="/dashboard">
                Erstelle dein erstes Projekt im Board.
              </Link>
            </p>
          )}
        </>
      )}
      {booking && (
        <WorkDialog
          title={`${booking.ticket.key} · ${booking.ticket.title}`}
          onClose={() => setBooking(null)}
          wide
        >
          <TicketTime
            ticket={booking.ticket}
            initialEntry={booking.entry}
            onSaved={async () => {
              setRevision((n) => n + 1);
            }}
          />
        </WorkDialog>
      )}
    </div>
  );
}
