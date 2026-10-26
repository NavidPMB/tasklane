"use client";
import { useState, type FormEvent } from "react";
import { type FieldDefinition, type ProjectData, workAction } from "@/lib/work";

export const fieldLabels: Record<FieldDefinition["kind"], string> = {
  text: "Text",
  textarea: "Langer Text",
  number: "Zahl",
  date: "Datum",
  boolean: "Ja / Nein",
  select: "Auswahl",
  multiselect: "Mehrfachauswahl",
  url: "Link",
};
export function FieldInput({
  field,
  value,
  onChange,
  disabled = false,
}: {
  field: FieldDefinition;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
}) {
  const label = field.name + (field.required ? " *" : "");
  if (field.kind === "boolean")
    return (
      <label className="tl-check-label">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        {label}
      </label>
    );
  if (field.kind === "multiselect")
    return (
      <fieldset>
        <legend>{label}</legend>
        <div className="tl-choices">
          {field.options.map((option) => (
            <label key={option} className="tl-choice">
              <input
                type="checkbox"
                checked={Array.isArray(value) && value.includes(option)}
                disabled={disabled}
                onChange={(e) => {
                  const values = Array.isArray(value) ? value : [];
                  onChange(
                    e.target.checked
                      ? [...values, option]
                      : values.filter((v) => v !== option),
                  );
                }}
              />
              {option}
            </label>
          ))}
        </div>
      </fieldset>
    );
  if (field.kind === "select")
    return (
      <label>
        {label}
        <select
          aria-label={label}
          value={typeof value === "string" ? value : ""}
          required={field.required}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">Bitte wählen</option>
          {field.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
    );
  if (field.kind === "textarea")
    return (
      <label>
        {label}
        <textarea
          aria-label={label}
          value={typeof value === "string" ? value : ""}
          maxLength={10000}
          rows={3}
          required={field.required}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  return (
    <label>
      {label}
      <input
        type={
          field.kind === "number"
            ? "number"
            : field.kind === "url"
              ? "url"
              : field.kind === "date"
                ? "date"
                : "text"
        }
        step={field.kind === "number" ? "any" : undefined}
        value={
          typeof value === "string" || typeof value === "number" ? value : ""
        }
        required={field.required}
        disabled={disabled}
        maxLength={field.kind === "url" ? 2000 : 1000}
        onChange={(e) =>
          onChange(
            field.kind === "number"
              ? e.target.value === ""
                ? null
                : Number(e.target.value)
              : e.target.value,
          )
        }
      />
    </label>
  );
}

export function CustomFieldsSettings({
  data,
  onSaved,
}: {
  data: ProjectData;
  onSaved: () => Promise<void>;
}) {
  const [kind, setKind] = useState<FieldDefinition["kind"]>("text"),
    [scope, setScope] = useState("ticket"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function run(action: string, args: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      await workAction(action, { project_id: data.project.id, ...args });
      await onSaved();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Änderung fehlgeschlagen.");
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      values = new FormData(form);
    const name = String(values.get("name"));
    const stem =
      name
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .slice(0, 50) || "feld";
    let key = /^[a-z]/.test(stem) ? stem : `feld_${stem}`;
    let suffix = 1;
    while (data.custom_fields.some((f) => f.key === key)) {
      suffix++;
      key = `${stem}_${suffix}`;
    }
    const ok = await run("create_custom_field", {
      key,
      name,
      kind,
      scope,
      required: values.get("required") === "on",
      options: ["select", "multiselect"].includes(kind)
        ? String(values.get("options") || "")
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      ...(scope === "project"
        ? { project_value: kind === "boolean" ? false : null }
        : {}),
    });
    if (ok) form.reset();
  }
  return (
    <div className="tl-field-settings">
      {error && (
        <p className="tl-error" role="alert">
          {error}
        </p>
      )}
      <p className="tl-hint">
        Eigene Felder gelten für dieses Projekt oder seine Tickets. Archivierte
        Felder behalten ihre Werte. Feldtypen und Schlüssel bleiben nach dem
        Anlegen stabil.
      </p>
      {data.custom_fields.map((field) => (
        <FieldSettingsRow
          key={`${field.id}-${field.updated_at}`}
          field={field}
          canManage={data.project.can_manage}
          busy={busy}
          run={run}
        />
      ))}
      {data.project.can_manage && (
        <form className="tl-form tl-inline-panel" onSubmit={create}>
          <h3>Eigenes Feld hinzufügen</h3>
          <label>
            Name
            <input
              name="name"
              required
              maxLength={120}
              placeholder="Zum Beispiel: Kundenreferenz"
            />
          </label>
          <div className="tl-form-grid">
            <label>
              Typ
              <select
                aria-label="Typ"
                value={kind}
                onChange={(e) =>
                  setKind(e.target.value as FieldDefinition["kind"])
                }
              >
                {Object.entries(fieldLabels).map(([key, label]) => (
                  <option value={key} key={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Gilt für
              <select aria-label="Gilt für" value={scope} onChange={(e) => setScope(e.target.value)}>
                <option value="ticket">Tickets</option>
                <option value="project">Dieses Projekt</option>
              </select>
            </label>
          </div>
          {["select", "multiselect"].includes(kind) && (
            <label>
              Optionen · eine pro Zeile
              <textarea name="options" required rows={4} maxLength={12000} />
            </label>
          )}
          {scope === "ticket" && (
            <label className="tl-check-label">
              <input type="checkbox" name="required" />
              Pflichtfeld bei neuen Tickets
            </label>
          )}
          <button className="button" disabled={busy}>
            Feld hinzufügen
          </button>
        </form>
      )}
    </div>
  );
}
function FieldSettingsRow({
  field,
  canManage,
  busy,
  run,
}: {
  field: FieldDefinition;
  canManage: boolean;
  busy: boolean;
  run: (action: string, args: Record<string, unknown>) => Promise<boolean>;
}) {
  const [name, setName] = useState(field.name),
    [options, setOptions] = useState(field.options.join("\n")),
    [value, setValue] = useState(field.project_value),
    [required, setRequired] = useState(field.required);
  return (
    <form
      className="tl-form tl-field-row"
      onSubmit={(e) => {
        e.preventDefault();
        void run("update_custom_field", {
          field_id: field.id,
          name,
          required,
          options: options
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
          expected_updated_at: field.updated_at,
          ...(field.scope === "project" ? { project_value: value } : {}),
        });
      }}
    >
      <div className="tl-panel-head">
        <strong>{field.name}</strong>
        <span className="tl-hint">
          {fieldLabels[field.kind]} ·{" "}
          {field.scope === "project" ? "Projekt" : "Tickets"}
          {field.archived ? " · archiviert" : ""}
        </span>
      </div>
      {canManage && (
        <label>
          Feldname
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={120}
          />
        </label>
      )}
      {field.scope === "project" && (
        <FieldInput
          field={field}
          value={value}
          onChange={setValue}
          disabled={!canManage || field.archived}
        />
      )}{" "}
      {canManage && !field.archived && (
        <>
          {["select", "multiselect"].includes(field.kind) && (
            <label>
              Optionen
              <textarea
                value={options}
                onChange={(e) => setOptions(e.target.value)}
                rows={3}
                maxLength={12000}
              />
            </label>
          )}
          {field.scope === "ticket" && (
            <label className="tl-check-label">
              <input
                type="checkbox"
                checked={required}
                onChange={(e) => setRequired(e.target.checked)}
              />
              Pflichtfeld bei neuen Tickets
            </label>
          )}
          <div className="tl-import-actions">
            <button className="tl-secondary" disabled={busy}>
              Feld speichern
            </button>
            <button
              type="button"
              className="tl-plain-button"
              disabled={busy}
              onClick={() =>
                void run("update_custom_field", {
                  field_id: field.id,
                  archived: true,
                  expected_updated_at: field.updated_at,
                })
              }
            >
              Archivieren
            </button>
          </div>
        </>
      )}
      {canManage && field.archived && (
        <button
          type="button"
          className="tl-secondary"
          disabled={busy}
          onClick={() =>
            void run("update_custom_field", {
              field_id: field.id,
              archived: false,
              expected_updated_at: field.updated_at,
            })
          }
        >
          Wieder aktivieren
        </button>
      )}
    </form>
  );
}
