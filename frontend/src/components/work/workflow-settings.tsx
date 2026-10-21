"use client";
import { useState, type FormEvent } from "react";
import { type ProjectData, type Status, workAction } from "@/lib/work";
import { WorkDialog } from "./dialog";

export function WorkflowSettings({
  data,
  onClose,
  onSaved,
}: {
  data: ProjectData;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [tab, setTab] = useState("workflow");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState(data.categories[0].id);
  const [after, setAfter] = useState("");
  const [deleting, setDeleting] = useState<Status | null>(null);
  async function run(
    action: string,
    args: Record<string, unknown>,
    afterSave?: () => void,
  ) {
    setBusy(true);
    setError("");
    try {
      await workAction(action, { project_id: data.project.id, ...args });
      await onSaved();
      afterSave?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Änderung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }
  function submit(
    event: FormEvent<HTMLFormElement>,
    action: string,
    extra: Record<string, unknown> = {},
    afterSave?: () => void,
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const args: Record<string, unknown> = Object.fromEntries(
      new FormData(form),
    );
    if (args.position) args.position = Number(args.position);
    void run(action, { ...args, ...extra }, afterSave || (() => form.reset()));
  }
  return (
    <WorkDialog title="Workflow & Team" onClose={onClose} wide>
      <div className="tl-tabs tl-settings-tabs">
        {[
          ["workflow", "Status"],
          ["tags", "Tags"],
          ["team", "Team & Projekt"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "active" : ""}
            onClick={() => {
              setTab(id);
              setError("");
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {error && (
        <p className="tl-error" role="alert">
          {error}
        </p>
      )}
      <div className="tl-settings-body">
        {tab === "workflow" && (
          <>
            <p className="tl-hint">
              Vier feste Grundkategorien, beliebig viele Zwischenstatus.
              Änderungen gelten auch für Board, Auswahlfelder und MCP.
            </p>
            {data.categories.map((c) => (
              <section key={c.id} className="tl-status-group">
                <h3>
                  <span className={`tl-dot tl-category-${c.id}`} />
                  {c.name}
                </h3>
                {data.statuses
                  .filter((s) => s.category === c.id)
                  .map((s, index, statuses) => (
                    <div
                      className="tl-status-row"
                      key={`${s.id}-${s.name}-${s.category}-${s.position}`}
                    >
                      <form
                        onSubmit={(event) =>
                          submit(
                            event,
                            "update_status",
                            { status_id: s.id },
                            () => {},
                          )
                        }
                      >
                        <input
                          name="name"
                          defaultValue={s.name}
                          required
                          maxLength={60}
                          aria-label={`Statusname ${s.name}`}
                        />
                        <select
                          name="category"
                          defaultValue={s.category}
                          disabled={s.is_base}
                          aria-label={`Kategorie für ${s.name}`}
                        >
                          {data.categories.map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {cat.name}
                            </option>
                          ))}
                        </select>
                        <button className="tl-secondary" disabled={busy}>
                          Speichern
                        </button>
                      </form>
                      {s.is_base ? (
                        <span className="tl-base-label">Grundstatus</span>
                      ) : (
                        <div className="tl-status-controls">
                          <button
                            className="tl-plain-button"
                            title="Nach oben"
                            aria-label={`${s.name} nach oben`}
                            disabled={busy || index < 2}
                            onClick={() =>
                              run("update_status", {
                                status_id: s.id,
                                position: statuses[index - 1].position,
                              })
                            }
                          >
                            ↑
                          </button>
                          <button
                            className="tl-plain-button"
                            title="Nach unten"
                            aria-label={`${s.name} nach unten`}
                            disabled={busy || index === statuses.length - 1}
                            onClick={() =>
                              run("update_status", {
                                status_id: s.id,
                                position: statuses[index + 1].position + 1,
                              })
                            }
                          >
                            ↓
                          </button>
                          <button
                            className="tl-plain-button tl-danger"
                            disabled={busy}
                            onClick={() => setDeleting(s)}
                          >
                            Entfernen
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
              </section>
            ))}
            <form
              className="tl-form tl-inline-panel"
              onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const args = {
                  name: new FormData(form).get("name"),
                  category,
                  ...(after ? { position: Number(after) + 1 } : {}),
                };
                void run("create_status", args, () => {
                  form.reset();
                  setAfter("");
                });
              }}
            >
              <h3>Zwischenstatus ergänzen</h3>
              <label>
                Name
                <input
                  name="name"
                  required
                  maxLength={60}
                  placeholder="Zum Beispiel: Review"
                />
              </label>
              <div className="tl-form-grid">
                <label>
                  Grundkategorie
                  <select
                    value={category}
                    onChange={(e) => {
                      setCategory(e.target.value);
                      setAfter("");
                    }}
                  >
                    {data.categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Position
                  <select
                    value={after}
                    onChange={(e) => setAfter(e.target.value)}
                  >
                    <option value="">Am Ende der Kategorie</option>
                    {data.statuses
                      .filter((s) => s.category === category)
                      .map((s) => (
                        <option key={s.id} value={s.position}>
                          Nach {s.name}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <button className="button" disabled={busy}>
                Status hinzufügen
              </button>
            </form>
            {deleting && (
              <form
                className="tl-form tl-inline-panel"
                onSubmit={(event) => {
                  event.preventDefault();
                  const replacement = new FormData(event.currentTarget).get(
                    "replacement",
                  );
                  void run(
                    "delete_status",
                    {
                      status_id: deleting.id,
                      ...(replacement
                        ? { replacement_status_id: Number(replacement) }
                        : {}),
                    },
                    () => setDeleting(null),
                  );
                }}
              >
                <h3>„{deleting.name}“ entfernen</h3>
                <p className="tl-hint">
                  Tickets bleiben erhalten und wechseln in den gewählten
                  Ersatzstatus.
                </p>
                <label>
                  Ersatzstatus
                  <select name="replacement" required defaultValue="">
                    <option value="" disabled>
                      Bitte auswählen
                    </option>
                    {data.statuses
                      .filter((s) => s.id !== deleting.id)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                  </select>
                </label>
                <div className="tl-form-actions">
                  <button
                    type="button"
                    className="tl-secondary"
                    onClick={() => setDeleting(null)}
                  >
                    Abbrechen
                  </button>
                  <button className="button" disabled={busy}>
                    Status entfernen
                  </button>
                </div>
              </form>
            )}
          </>
        )}
        {tab === "tags" && (
          <>
            <p className="tl-hint">
              Gemeinsame Tags für alle Tickets in diesem Projekt.
            </p>
            <div className="tl-tag-settings">
              {data.tags.map((t) => (
                <form
                  key={`${t.id}-${t.name}`}
                  className="tl-tag-setting"
                  onSubmit={(e) =>
                    submit(e, "update_tag", { tag_id: t.id }, () => {})
                  }
                >
                  <span className="tl-tag-symbol">#</span>
                  <input
                    name="name"
                    defaultValue={t.name}
                    aria-label={`Tag ${t.name}`}
                    required
                    maxLength={40}
                  />
                  <button className="tl-secondary" disabled={busy}>
                    Speichern
                  </button>
                  <button
                    type="button"
                    className="tl-plain-button tl-danger"
                    disabled={busy}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Tag „${t.name}“ von allen Tickets entfernen?`,
                        )
                      )
                        void run("delete_tag", { tag_id: t.id });
                    }}
                  >
                    Entfernen
                  </button>
                </form>
              ))}
            </div>
            <form
              className="tl-form tl-inline-panel"
              onSubmit={(e) => submit(e, "create_tag")}
            >
              <h3>Neuer Tag</h3>
              <label>
                Name
                <input
                  name="name"
                  required
                  maxLength={40}
                  placeholder="Zum Beispiel: Frontend"
                />
              </label>
              <button className="button" disabled={busy}>
                Tag hinzufügen
              </button>
            </form>
          </>
        )}
        {tab === "team" && (
          <>
            <h3>Projektmitglieder</h3>
            <div className="tl-members">
              {data.members.map((u) => (
                <div className="tl-member" key={u.id}>
                  <span className="tl-avatar">
                    {u.name.charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <strong>{u.name}</strong>
                    <small>{u.email}</small>
                  </div>
                  {u.id === data.project.owner_id ? (
                    <span className="tl-base-label">Projektleitung</span>
                  ) : (
                    data.project.can_manage && (
                      <button
                        className="tl-plain-button tl-danger"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `${u.name} entfernen und dessen Zuweisungen lösen?`,
                            )
                          )
                            void run("remove_project_member", {
                              user_id: u.id,
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
            {data.project.can_manage ? (
              <>
                <form
                  className="tl-form tl-inline-panel"
                  onSubmit={(e) => submit(e, "add_project_member")}
                >
                  <h3>Mitglied hinzufügen</h3>
                  <label>
                    E-Mail-Adresse
                    <input
                      type="email"
                      name="email"
                      required
                      maxLength={254}
                      placeholder="name@team.de"
                    />
                  </label>
                  <p className="tl-hint">
                    Das Teammitglied benötigt bereits ein aktives
                    Tasklane-Konto.
                  </p>
                  <button className="button" disabled={busy}>
                    Hinzufügen
                  </button>
                </form>
                <form
                  className="tl-form tl-inline-panel"
                  key={data.project.name + data.project.description}
                  onSubmit={(e) => submit(e, "update_project", {}, () => {})}
                >
                  <h3>Projekteinstellungen</h3>
                  <label>
                    Name
                    <input
                      name="name"
                      defaultValue={data.project.name}
                      required
                      maxLength={120}
                    />
                  </label>
                  <label>
                    Beschreibung
                    <textarea
                      name="description"
                      defaultValue={data.project.description}
                      rows={3}
                      maxLength={10000}
                    />
                  </label>
                  <p className="tl-hint">
                    Das Kürzel {data.project.key} bleibt für bestehende
                    Ticketverweise fest.
                  </p>
                  <button className="button" disabled={busy}>
                    Projekt speichern
                  </button>
                </form>
              </>
            ) : (
              <p className="tl-hint">
                Die Projektleitung verwaltet Mitglieder und
                Projekteinstellungen.
              </p>
            )}
          </>
        )}
      </div>
    </WorkDialog>
  );
}
