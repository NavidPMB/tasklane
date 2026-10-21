"use client";
import { useState, type FormEvent } from "react";
import {
  type ProjectData,
  type Ticket,
  priorities,
  workAction,
} from "@/lib/work";
import { WorkDialog } from "./dialog";
import { TicketTime } from "./ticket-time";
import { formatMinutes } from "@/lib/time";

export function TicketForm({
  data,
  ticket,
  parentId,
  initialStatus,
  initialKind,
  onClose,
  onSaved,
}: {
  data: ProjectData;
  ticket?: Ticket;
  parentId?: number;
  initialStatus?: number;
  initialKind?: "epic" | "ticket";
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [kind, setKind] = useState(ticket?.kind || initialKind || "ticket");
  const [tab, setTab] = useState("details");
  const loggedMinutes =
    data.tickets.find((t) => t.id === ticket?.id)?.logged_minutes || 0;
  const [parent, setParent] = useState(
    String(ticket?.parent_id || parentId || ""),
  );
  const [assignees, setAssignees] = useState<number[]>(
    ticket?.assignee_ids || [],
  );
  const [tags, setTags] = useState<number[]>(ticket?.tag_ids || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blockedParents = new Set<number>(ticket ? [ticket.id] : []);
  let changed = true;
  while (changed) {
    changed = false;
    for (const candidate of data.tickets) {
      if (
        candidate.parent_id &&
        blockedParents.has(candidate.parent_id) &&
        !blockedParents.has(candidate.id)
      ) {
        blockedParents.add(candidate.id);
        changed = true;
      }
    }
  }
  const children = ticket
    ? data.tickets.filter((t) => t.parent_id === ticket.id)
    : [];
  const toggle = (items: number[], id: number) =>
    items.includes(id) ? items.filter((i) => i !== id) : [...items, id];

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const args = {
        project_id: data.project.id,
        title: form.get("title"),
        description: form.get("description"),
        kind,
        parent_id: kind === "epic" ? null : parent ? Number(parent) : null,
        status_id: Number(form.get("status_id")),
        assignee_ids: assignees,
        tag_ids: tags,
        priority: form.get("priority"),
        due_date: form.get("due_date") || null,
        ...(ticket
          ? { ticket_id: ticket.id, expected_updated_at: ticket.updated_at }
          : {}),
      };
      await workAction(ticket ? "update_ticket" : "create_ticket", args);
      await onSaved();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Speichern fehlgeschlagen.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!ticket || !window.confirm(`${ticket.key} wirklich löschen?`)) return;
    setBusy(true);
    setError("");
    try {
      await workAction("delete_ticket", {
        project_id: data.project.id,
        ticket_id: ticket.id,
      });
      await onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkDialog
      title={
        ticket
          ? `${ticket.key} bearbeiten`
          : kind === "epic"
            ? "Neues Epic"
            : parentId
              ? "Neues Unterticket"
              : "Neues Ticket"
      }
      onClose={onClose}
      wide
    >
      {ticket && (
        <div className="tl-tabs tl-settings-tabs">
          <button
            type="button"
            className={tab === "details" ? "active" : ""}
            onClick={() => setTab("details")}
          >
            Ticketdetails
          </button>
          <button
            type="button"
            className={tab === "time" ? "active" : ""}
            onClick={() => setTab("time")}
          >
            Zeit erfassen
            {loggedMinutes > 0 ? ` · ${formatMinutes(loggedMinutes)}` : ""}
          </button>
        </div>
      )}
      {ticket?.jira && (
        <p className="tl-hint" style={{ padding: "0 24px" }}>
          Importiert aus Jira:{" "}
          <a href={ticket.jira.url} target="_blank" rel="noreferrer">
            {ticket.jira.key} ↗
          </a>
        </p>
      )}
      <div hidden={tab !== "details"}>
        <form onSubmit={save} className="tl-form">
          {error && (
            <p className="tl-error" role="alert">
              {error}
            </p>
          )}
          <label>
            Titel
            <input
              name="title"
              defaultValue={ticket?.title}
              required
              maxLength={200}
              placeholder="Was ist zu tun?"
              autoFocus
            />
          </label>
          <label>
            Beschreibung
            <textarea
              name="description"
              defaultValue={ticket?.description}
              rows={5}
              maxLength={20000}
              placeholder="Kontext, Ziel und nächste Schritte …"
            />
          </label>
          <div className="tl-form-grid">
            <label>
              Typ
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as "epic" | "ticket")}
              >
                <option value="ticket">Ticket</option>
                <option value="epic">Epic</option>
              </select>
            </label>
            <label>
              Status
              <select
                name="status_id"
                defaultValue={
                  ticket?.status_id || initialStatus || data.statuses[0]?.id
                }
                required
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
            </label>
            <label>
              Priorität
              <select
                name="priority"
                defaultValue={ticket?.priority || "normal"}
              >
                {Object.entries(priorities).map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Fällig am
              <input
                type="date"
                name="due_date"
                defaultValue={ticket?.due_date || ""}
              />
            </label>
          </div>
          {kind !== "epic" && (
            <label>
              Übergeordnetes Epic / Ticket
              <select
                value={parent}
                onChange={(e) => setParent(e.target.value)}
              >
                <option value="">Kein übergeordnetes Ticket</option>
                {data.tickets
                  .filter((t) => !blockedParents.has(t.id))
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.kind === "epic" ? "Epic · " : ""}
                      {t.key} · {t.title}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <fieldset>
            <legend>Zuweisen</legend>
            <div className="tl-choices">
              {data.members.map((u) => (
                <label key={u.id} className="tl-choice">
                  <input
                    type="checkbox"
                    checked={assignees.includes(u.id)}
                    onChange={() => setAssignees(toggle(assignees, u.id))}
                  />
                  <span className="tl-mini-avatar" aria-hidden="true">
                    {u.name.charAt(0).toUpperCase()}
                  </span>
                  {u.name}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>Tags</legend>
            {data.tags.length ? (
              <div className="tl-choices">
                {data.tags.map((t) => (
                  <label key={t.id} className="tl-choice">
                    <input
                      type="checkbox"
                      checked={tags.includes(t.id)}
                      onChange={() => setTags(toggle(tags, t.id))}
                    />
                    {t.name}
                  </label>
                ))}
              </div>
            ) : (
              <p className="tl-hint">
                Tags kannst du unter „Workflow & Team“ anlegen.
              </p>
            )}
          </fieldset>
          {children.length > 0 && (
            <div className="tl-child-summary">
              <strong>
                {children.length} Unterticket{children.length > 1 ? "s" : ""}
              </strong>
              {children.map((t) => (
                <p key={t.id}>
                  {t.key} · {t.title}
                </p>
              ))}
            </div>
          )}
          <div className="tl-form-actions">
            {ticket && (
              <button
                type="button"
                className="tl-danger tl-plain-button"
                disabled={busy || children.length > 0}
                onClick={remove}
              >
                Löschen
              </button>
            )}
            <button
              type="button"
              className="tl-secondary"
              onClick={onClose}
              disabled={busy}
            >
              Abbrechen
            </button>
            <button className="button" disabled={busy}>
              {busy
                ? "Speichert …"
                : ticket
                  ? "Änderungen speichern"
                  : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
      {ticket && (
        <div hidden={tab !== "time"}>
          <TicketTime ticket={ticket} onSaved={onSaved} />
        </div>
      )}
    </WorkDialog>
  );
}
