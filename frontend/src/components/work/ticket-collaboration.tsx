"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import {
  type Person,
  type ProjectData,
  type Ticket,
  workAction,
  uploadFile,
} from "@/lib/work";

type Comment = {
  id: number;
  body: string;
  author: Person;
  deleted: boolean;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
};
type Item = {
  id: number;
  title: string;
  done: boolean;
  position: number;
  assignee_id: number | null;
  updated_at: string;
};
type Checklist = {
  id: number;
  name: string;
  position: number;
  updated_at: string;
  items: Item[];
};
type Attachment = {
  id: string;
  filename: string;
  size: number;
  sha256: string;
  comment_id: number | null;
  uploaded_by: number;
  download_url: string;
  created_at: string;
};
type Activity = {
  id: number;
  summary: string;
  actor: Person;
  created_at: string;
};
function when(value: string) {
  return new Date(value).toLocaleString("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
function bytes(value: number) {
  return value < 1024
    ? `${value} B`
    : value < 1048576
      ? `${(value / 1024).toLocaleString("de-DE", { maximumFractionDigits: 1 })} KiB`
      : `${(value / 1048576).toLocaleString("de-DE", { maximumFractionDigits: 1 })} MiB`;
}
export function TicketCollaboration({
  data,
  ticket,
  tab,
  userId,
  onSaved,
  onTab,
}: {
  data: ProjectData;
  ticket: Ticket;
  tab: string;
  userId: number;
  onSaved: () => Promise<void>;
  onTab: (tab: string) => void;
}) {
  const [comments, setComments] = useState<Comment[]>([]),
    [commentTotal, setCommentTotal] = useState(0),
    [lists, setLists] = useState<Checklist[]>([]),
    [files, setFiles] = useState<Attachment[]>([]),
    [events, setEvents] = useState<Activity[]>([]),
    [eventTotal, setEventTotal] = useState(0),
    [maxBytes, setMaxBytes] = useState(52428800);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [notice, setNotice] = useState("");
  const [body, setBody] = useState(""),
    [editing, setEditing] = useState<Comment | null>(null),
    [commentId, setCommentId] = useState("");
  const [commentLimit, setCommentLimit] = useState(50),
    [eventLimit, setEventLimit] = useState(50);
  const active = ["comments", "files", "checklists", "activity"].includes(tab);
  const refresh = useCallback(async () => {
    const common = { project_id: data.project.id, ticket_id: ticket.id };
    const [commentPages, l, f, activityPages] = await Promise.all([
      Promise.all(
        Array.from({ length: Math.ceil(commentLimit / 50) }, (_, index) =>
          workAction<{ comments: Comment[]; total: number }>("list_comments", {
            ...common,
            offset: index * 50,
            limit: 50,
          }),
        ),
      ),
      workAction<{ checklists: Checklist[] }>("list_checklists", common),
      workAction<{ attachments: Attachment[]; max_file_bytes: number }>(
        "list_attachments",
        common,
      ),
      Promise.all(
        Array.from({ length: Math.ceil(eventLimit / 50) }, (_, index) =>
          workAction<{ events: Activity[]; total: number }>("list_activity", {
            ...common,
            offset: index * 50,
            limit: 50,
          }),
        ),
      ),
    ]);
    const c = {
      comments: commentPages.flatMap((p) => p.comments),
      total: commentPages[0].total,
    };
    const a = {
      events: Array.from(
        new Map(
          activityPages.flatMap((p) => p.events).map((e) => [e.id, e]),
        ).values(),
      ),
      total: activityPages[0].total,
    };
    return { c, l, f, a };
  }, [data.project.id, ticket.id, commentLimit, eventLimit]);
  const apply = useCallback((r: Awaited<ReturnType<typeof refresh>>) => {
    setComments(r.c.comments);
    setCommentTotal(r.c.total);
    setLists(r.l.checklists);
    setFiles(r.f.attachments);
    setMaxBytes(r.f.max_file_bytes);
    setEvents(r.a.events);
    setEventTotal(r.a.total);
  }, []);
  useEffect(() => {
    if (!active) return;
    let mounted = true;
    let running = false;
    async function load() {
      if (document.hidden || running) return;
      running = true;
      try {
        const r = await refresh();
        if (mounted) {
          apply(r);
          setError("");
        }
      } catch (err) {
        if (mounted)
          setError(
            err instanceof Error ? err.message : "Laden fehlgeschlagen.",
          );
      } finally {
        running = false;
        if (mounted) setLoading(false);
      }
    }
    void load();
    const id = setInterval(load, 10000);
    window.addEventListener("focus", load);
    return () => {
      mounted = false;
      clearInterval(id);
      window.removeEventListener("focus", load);
    };
  }, [active, refresh, apply]);
  async function run(
    action: string,
    args: Record<string, unknown>,
    after?: () => void,
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await workAction(action, {
        project_id: data.project.id,
        ticket_id: ticket.id,
        ...args,
      });
      apply(await refresh());
      after?.();
      await onSaved();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Änderung fehlgeschlagen.");
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function comment(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await run(
      editing ? "update_comment" : "create_comment",
      {
        body,
        ...(editing
          ? { comment_id: editing.id, expected_updated_at: editing.updated_at }
          : {}),
      },
      () => {
        setBody("");
        setEditing(null);
      },
    );
  }
  async function upload(incoming: File[]) {
    if (!incoming.length || busy) return;
    if (incoming.some((file) => file.size > maxBytes)) {
      setError(`Eine Datei darf höchstens ${bytes(maxBytes)} groß sein.`);
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      for (let i = 0; i < incoming.length; i++) {
        setNotice(`Datei ${i + 1} von ${incoming.length} wird hochgeladen …`);
        await uploadFile(
          data.project.id,
          ticket.id,
          incoming[i],
          commentId ? Number(commentId) : undefined,
        );
      }
      apply(await refresh());
      await onSaved();
      setNotice("Dateien hochgeladen.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
      setNotice("");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="tl-collaboration"
      hidden={!active}
      aria-busy={busy || loading}
    >
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
      {tab === "comments" && (
        <>
          <form className="tl-form" onSubmit={comment}>
            <label>
              {editing ? "Kommentar bearbeiten" : "Neuer Kommentar"}
              <textarea
                aria-label={editing ? "Kommentar bearbeiten" : "Neuer Kommentar"}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                required
                maxLength={20000}
                rows={4}
                placeholder="Kontext, Rückfragen oder ein Update …"
                disabled={busy}
              />
            </label>
            <p className="tl-hint">
              Markdown wird unterstützt. Nur eigene Kommentare können bearbeitet
              oder entfernt werden.
            </p>
            <div className="tl-import-actions">
              {editing && (
                <button
                  type="button"
                  className="tl-secondary"
                  onClick={() => {
                    setEditing(null);
                    setBody("");
                  }}
                >
                  Abbrechen
                </button>
              )}
              <button className="button" disabled={busy || !body.trim()}>
                {editing ? "Kommentar speichern" : "Kommentar hinzufügen"}
              </button>
            </div>
          </form>
          <div className="tl-comments">
            {comments.map((c) => (
              <article key={c.id} className="tl-comment">
                <header>
                  <strong>{c.author.name || "Importierte Person"}</strong>
                  <time dateTime={c.created_at}>{when(c.created_at)}</time>
                </header>
                {c.deleted ? (
                  <p className="tl-hint">Kommentar entfernt.</p>
                ) : (
                  <div className="tl-markdown">
                    <ReactMarkdown skipHtml components={{ img: () => null }}>
                      {c.body}
                    </ReactMarkdown>
                  </div>
                )}
                <div className="tl-import-actions">
                  {c.can_edit && (
                    <>
                      <button
                        className="tl-plain-button"
                        disabled={busy}
                        onClick={() => {
                          setEditing(c);
                          setBody(c.body);
                        }}
                      >
                        Bearbeiten
                      </button>
                      <button
                        className="tl-plain-button tl-danger"
                        disabled={busy}
                        onClick={() => {
                          if (window.confirm("Diesen Kommentar entfernen?"))
                            void run("delete_comment", {
                              comment_id: c.id,
                              expected_updated_at: c.updated_at,
                            });
                        }}
                      >
                        Entfernen
                      </button>
                    </>
                  )}
                  {!c.deleted && (
                    <button
                      className="tl-plain-button"
                      onClick={() => {
                        setCommentId(String(c.id));
                        onTab("files");
                      }}
                    >
                      Datei anhängen
                    </button>
                  )}
                </div>
                {files
                  .filter((f) => f.comment_id === c.id)
                  .map((f) => (
                    <p key={f.id}>
                      <a href={f.download_url} download={f.filename}>
                        {f.filename}
                      </a>
                      <small> · {bytes(f.size)}</small>
                    </p>
                  ))}
              </article>
            ))}
          </div>
          {!comments.length && !loading && (
            <p className="tl-hint">Noch keine Kommentare.</p>
          )}
          {comments.length < commentTotal && (
            <button
              className="tl-secondary"
              onClick={() => setCommentLimit((n) => n + 50)}
            >
              Weitere Kommentare laden
            </button>
          )}
        </>
      )}
      {tab === "files" && (
        <>
          <div className="tl-form">
            <label>
              Dateien gehören zu
              <select
                aria-label="Dateien gehören zu"
                value={commentId}
                onChange={(e) => setCommentId(e.target.value)}
                disabled={busy}
              >
                <option value="">Diesem Ticket</option>
                {comments
                  .filter((c) => !c.deleted)
                  .map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.author.name} · {c.body.slice(0, 70)}
                    </option>
                  ))}
              </select>
            </label>
            <label
              className={`tl-upload-zone ${busy ? "is-busy" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                void upload(Array.from(e.dataTransfer.files));
              }}
            >
              <strong>Dateien auswählen oder hier ablegen</strong>
              <span>
                Bis {bytes(maxBytes)} je Datei · nur für Projektmitglieder
              </span>
              <input
                aria-label="Dateien hochladen"
                type="file"
                multiple
                disabled={busy}
                onChange={(e) => {
                  void upload(Array.from(e.target.files || []));
                  e.target.value = "";
                }}
              />
            </label>
          </div>
          <div className="tl-attachments">
            {files.map((f) => (
              <article className="tl-attachment" key={f.id}>
                <div>
                  <a href={f.download_url} download={f.filename}>
                    {f.filename}
                  </a>
                  <small>
                    {bytes(f.size)} · {when(f.created_at)}
                    {f.comment_id ? " · Kommentar" : ""}
                  </small>
                  <details>
                    <summary>Prüfsumme</summary>
                    <code>{f.sha256}</code>
                  </details>
                </div>
                {(f.uploaded_by === userId || data.project.can_manage) && (
                  <button
                    className="tl-plain-button tl-danger"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm(`„${f.filename}“ entfernen?`))
                        void run("delete_attachment", { attachment_id: f.id });
                    }}
                  >
                    Entfernen
                  </button>
                )}
              </article>
            ))}
          </div>
          {!files.length && !loading && (
            <p className="tl-hint">Noch keine Dateien angehängt.</p>
          )}
        </>
      )}
      {tab === "checklists" && (
        <>
          <form
            className="tl-form tl-inline-panel"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              void run(
                "create_checklist",
                { name: new FormData(form).get("name") },
                () => form.reset(),
              );
            }}
          >
            <label>
              Neue Checkliste
              <input
                name="name"
                required
                maxLength={120}
                placeholder="Zum Beispiel: Abnahme"
                disabled={busy}
              />
            </label>
            <button className="button" disabled={busy}>
              Checkliste hinzufügen
            </button>
          </form>
          {lists.map((list) => (
            <ChecklistPanel
              key={list.id}
              list={list}
              data={data}
              busy={busy}
              run={run}
            />
          ))}
        </>
      )}
      {tab === "activity" && (
        <>
          <h3>Ticketverlauf</h3>
          <ol className="tl-activity">
            {events.map((event) => (
              <li key={event.id}>
                <strong>{event.summary}</strong>
                <span>
                  {event.actor.name} · {when(event.created_at)}
                </span>
              </li>
            ))}
          </ol>
          {events.length < eventTotal && (
            <button
              className="tl-secondary"
              onClick={() => setEventLimit((n) => n + 50)}
            >
              Weitere Aktivitäten laden
            </button>
          )}
          {!events.length && !loading && (
            <p className="tl-hint">
              Für dieses Ticket sind noch keine Ereignisse erfasst.
            </p>
          )}
        </>
      )}
    </div>
  );
}
function ChecklistPanel({
  list,
  data,
  busy,
  run,
}: {
  list: Checklist;
  data: ProjectData;
  busy: boolean;
  run: (
    action: string,
    args: Record<string, unknown>,
    after?: () => void,
  ) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState<Item | null>(null),
    [title, setTitle] = useState("");
  return (
    <section className="tl-checklist">
      <div className="tl-panel-head">
        <h3>
          {list.name}{" "}
          <small>
            {list.items.filter((i) => i.done).length}/{list.items.length}
          </small>
        </h3>
        <button
          className="tl-plain-button"
          disabled={busy}
          onClick={() => {
            const name = window.prompt("Name der Checkliste", list.name);
            if (name?.trim())
              void run("update_checklist", {
                checklist_id: list.id,
                name: name.trim(),
                expected_updated_at: list.updated_at,
              });
          }}
        >
          Umbenennen
        </button>
        <button
          className="tl-plain-button tl-danger"
          disabled={busy}
          onClick={() => {
            if (
              window.confirm(
                `Checkliste „${list.name}“ mit allen Punkten entfernen?`,
              )
            )
              void run("delete_checklist", {
                checklist_id: list.id,
                expected_updated_at: list.updated_at,
              });
          }}
        >
          Entfernen
        </button>
      </div>
      <progress
        value={list.items.filter((i) => i.done).length}
        max={list.items.length || 1}
        aria-label={`Fortschritt ${list.name}`}
      />
      <ul>
        {list.items.map((item, index) => (
          <li key={item.id}>
            <label className="tl-check-label">
              <input
                type="checkbox"
                checked={item.done}
                disabled={busy}
                onChange={(e) =>
                  void run("update_checklist_item", {
                    checklist_id: list.id,
                    item_id: item.id,
                    done: e.target.checked,
                    expected_updated_at: item.updated_at,
                  })
                }
              />
              <span className={item.done ? "tl-done-text" : ""}>
                {item.title}
              </span>
            </label>
            <select
              aria-label={`Zuständig für ${item.title}`}
              value={item.assignee_id || ""}
              disabled={busy}
              onChange={(e) =>
                void run("update_checklist_item", {
                  checklist_id: list.id,
                  item_id: item.id,
                  assignee_id: e.target.value ? Number(e.target.value) : null,
                  expected_updated_at: item.updated_at,
                })
              }
            >
              <option value="">Nicht zugewiesen</option>
              {data.members.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <div className="tl-checklist-actions">
              <button
                className="tl-plain-button"
                disabled={busy}
                onClick={() => {
                  setEditing(item);
                  setTitle(item.title);
                }}
              >
                Bearbeiten
              </button>
              <button
                className="tl-plain-button"
                title="Nach oben"
                aria-label={`${item.title} nach oben`}
                disabled={busy || index === 0}
                onClick={() =>
                  void run("update_checklist_item", {
                    checklist_id: list.id,
                    item_id: item.id,
                    position: Math.max(0, list.items[index - 1].position - 1),
                    expected_updated_at: item.updated_at,
                  })
                }
              >
                ↑
              </button>
              <button
                className="tl-plain-button tl-danger"
                disabled={busy}
                onClick={() =>
                  void run("delete_checklist_item", {
                    checklist_id: list.id,
                    item_id: item.id,
                    expected_updated_at: item.updated_at,
                  })
                }
              >
                Entfernen
              </button>
            </div>
          </li>
        ))}
      </ul>
      <form
        className="tl-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run(
            editing ? "update_checklist_item" : "create_checklist_item",
            {
              checklist_id: list.id,
              title,
              ...(editing
                ? {
                    item_id: editing.id,
                    expected_updated_at: editing.updated_at,
                  }
                : {}),
            },
            () => {
              setTitle("");
              setEditing(null);
            },
          );
        }}
      >
        <label>
          {editing ? "Punkt bearbeiten" : "Neuer Punkt"}
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={500}
            disabled={busy}
          />
        </label>
        <div className="tl-import-actions">
          {editing && (
            <button
              type="button"
              className="tl-secondary"
              onClick={() => {
                setEditing(null);
                setTitle("");
              }}
            >
              Abbrechen
            </button>
          )}
          <button className="tl-secondary" disabled={busy || !title.trim()}>
            {editing ? "Punkt speichern" : "Punkt hinzufügen"}
          </button>
        </div>
      </form>
    </section>
  );
}
