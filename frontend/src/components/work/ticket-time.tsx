"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { Ticket } from "@/lib/work";
import { workAction, workFetch } from "@/lib/work";
import {
  type TimeEntry,
  type TimeEntries,
  formatMinutes,
  localDate,
  displayDate,
} from "@/lib/time";

export type TimeTicket = Pick<Ticket, "id" | "project_id" | "key" | "title">;
export function TicketTime({
  ticket,
  onSaved,
  initialEntry,
}: {
  ticket: TimeTicket;
  onSaved: () => Promise<void>;
  initialEntry?: TimeEntry;
}) {
  const [result, setResult] = useState<TimeEntries | null>(null);
  const [editing, setEditing] = useState<TimeEntry | null>(
    initialEntry || null,
  );
  const [date, setDate] = useState(initialEntry?.work_date || localDate());
  const [hours, setHours] = useState(
    String(Math.floor((initialEntry?.minutes || 30) / 60)),
  );
  const [minutes, setMinutes] = useState(
    String((initialEntry?.minutes || 30) % 60),
  );
  const [note, setNote] = useState(initialEntry?.note || "");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  const pageSize = 10;
  useEffect(() => {
    const controller = new AbortController();
    workFetch<TimeEntries>(
      `/api/work/time/entries/?project_id=${ticket.project_id}&ticket_id=${ticket.id}&offset=${offset}&limit=${pageSize}`,
      controller.signal,
    )
      .then((data) => {
        if (!controller.signal.aborted) setResult(data);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setResult(null);
          setError(err.message);
        }
      });
    return () => controller.abort();
  }, [ticket.id, ticket.project_id, offset, revision]);
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
  const reset = useCallback(() => {
    setEditing(null);
    setDate(localDate());
    setHours("0");
    setMinutes("30");
    setNote("");
  }, []);
  function edit(entry: TimeEntry) {
    setEditing(entry);
    setDate(entry.work_date);
    setHours(String(Math.floor(entry.minutes / 60)));
    setMinutes(String(entry.minutes % 60));
    setNote(entry.note);
    setError("");
    setNotice("");
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const total = Number(hours) * 60 + Number(minutes);
    if (!Number.isInteger(total) || total < 1 || total > 1440) {
      setError("Bitte eine Dauer zwischen 1 Minute und 24 Stunden eingeben.");
      setBusy(false);
      return;
    }
    try {
      await workAction(editing ? "update_time_entry" : "create_time_entry", {
        project_id: ticket.project_id,
        work_date: date,
        minutes: total,
        note,
        ...(editing
          ? { entry_id: editing.id, expected_updated_at: editing.updated_at }
          : { ticket_id: ticket.id }),
      });
      reset();
      setOffset(0);
      setRevision((n) => n + 1);
      await onSaved();
      setNotice("Arbeitszeit gespeichert.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Zeit konnte nicht gespeichert werden.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove(entry: TimeEntry) {
    if (
      !window.confirm(
        `${formatMinutes(entry.minutes)} vom ${displayDate(entry.work_date)} wirklich löschen?`,
      )
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await workAction("delete_time_entry", {
        project_id: ticket.project_id,
        entry_id: entry.id,
        expected_updated_at: entry.updated_at,
      });
      if (editing?.id === entry.id) reset();
      setOffset(0);
      setRevision((n) => n + 1);
      await onSaved();
      setNotice("Zeitbuchung gelöscht.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="tl-time-panel">
      <div className="tl-time-summary">
        <div>
          <span className="eyebrow">GEBUCHTE ARBEITSZEIT</span>
          <strong>{formatMinutes(result?.total_minutes || 0)}</strong>
        </div>
        <span className="tl-hint">
          {result?.total || 0} Buchungen · {ticket.key}
        </span>
      </div>
      {error && (
        <p className="tl-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="tl-time-notice" role="status">
          {notice}
        </p>
      )}
      <form
        className="tl-form tl-time-form"
        onSubmit={save}
        aria-label={editing ? "Zeitbuchung bearbeiten" : "Arbeitszeit buchen"}
      >
        <h3>{editing ? "Eigene Buchung bearbeiten" : "Arbeitszeit buchen"}</h3>
        <div className="tl-time-inputs">
          <label>
            Datum
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              max={localDate()}
              required
              disabled={busy}
            />
          </label>
          <label>
            Stunden
            <input
              type="number"
              min={0}
              max={24}
              step={1}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              required
              disabled={busy}
            />
          </label>
          <label>
            Minuten
            <input
              type="number"
              min={0}
              max={59}
              step={1}
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              required
              disabled={busy}
            />
          </label>
        </div>
        <label>
          Notiz
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={2000}
            rows={2}
            placeholder="Woran hast du gearbeitet?"
            disabled={busy}
          />
        </label>
        <div className="tl-time-form-footer">
          <span className="tl-hint">
            Die Buchung wird deinem Konto zugeordnet.
          </span>
          <div>
            {editing && (
              <button
                type="button"
                className="tl-secondary"
                onClick={reset}
                disabled={busy}
              >
                Abbrechen
              </button>
            )}
            <button className="button" disabled={busy}>
              {busy
                ? "Speichert …"
                : editing
                  ? "Buchung speichern"
                  : "Zeit buchen"}
            </button>
          </div>
        </div>
      </form>
      <h3 className="tl-time-history-heading">Buchungen auf diesem Ticket</h3>
      <div className="tl-time-history">
        {result?.entries.map((entry) => (
          <article key={entry.id} className="tl-time-entry">
            <div className="tl-time-entry-top">
              <strong>{formatMinutes(entry.minutes)}</strong>
              <span>
                {displayDate(entry.work_date)} · {entry.user.name}
              </span>
              {entry.can_edit && (
                <div>
                  <button
                    className="tl-plain-button"
                    disabled={busy}
                    onClick={() => edit(entry)}
                  >
                    Bearbeiten
                  </button>
                  <button
                    className="tl-plain-button tl-danger"
                    disabled={busy}
                    onClick={() => remove(entry)}
                  >
                    Löschen
                  </button>
                </div>
              )}
            </div>
            {entry.source && (
              <p className="tl-hint">
                ClickUp-Historie · Originalperson: {entry.source.person} ·
                Quell-ID {entry.source.id}
              </p>
            )}
            {entry.note && <p>{entry.note}</p>}
          </article>
        ))}
        {result?.entries.length === 0 && (
          <p className="tl-hint">
            Für dieses Ticket wurde noch keine Zeit gebucht.
          </p>
        )}
        {!result && !error && (
          <p className="tl-hint" role="status">
            Zeitbuchungen werden geladen …
          </p>
        )}
      </div>
      {result && result.total > pageSize && (
        <div className="tl-time-pagination">
          <button
            className="tl-secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - pageSize))}
          >
            Zurück
          </button>
          <span>
            {offset + 1}–{Math.min(offset + pageSize, result.total)} von{" "}
            {result.total}
          </span>
          <button
            className="tl-secondary"
            disabled={offset + pageSize >= result.total}
            onClick={() => setOffset(offset + pageSize)}
          >
            Weiter
          </button>
        </div>
      )}
    </div>
  );
}
