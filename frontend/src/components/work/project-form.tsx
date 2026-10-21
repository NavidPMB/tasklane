"use client";
import { useState, type FormEvent } from "react";
import { workAction, type Project, type Workspace } from "@/lib/work";
import { WorkDialog } from "./dialog";

export function ProjectForm({
  onClose,
  onSaved,
  workspaces,
  workspaceId,
}: {
  workspaces: Workspace[];
  workspaceId?: number;
  onClose: () => void;
  onSaved: (project: Project) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const project = await workAction<Project>("create_project", {
        ...Object.fromEntries(form),
        workspace_id: Number(form.get("workspace_id")),
      });
      await onSaved(project);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Projekt konnte nicht erstellt werden.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <WorkDialog title="Neues Projekt" onClose={onClose}>
      <form className="tl-form" onSubmit={save}>
        <p className="tl-hint">
          Ein eigener Bereich für dein Team, mit vier Grundstatus und einem
          anpassbaren Workflow.
        </p>
        {error && (
          <p className="tl-error" role="alert">
            {error}
          </p>
        )}
        <label>
          Workspace
          <select
            name="workspace_id"
            required
            defaultValue={
              workspaceId || workspaces.find((w) => w.can_create_project)?.id
            }
          >
            {workspaces
              .filter((w) => w.can_create_project)
              .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
          </select>
        </label>
        {!workspaces.some((w) => w.can_create_project) && (
          <p className="tl-hint">
            Bitte zuerst unter Workspaces einen Workspace erstellen.
          </p>
        )}
        <label>
          Projektname
          <input
            name="name"
            placeholder="Zum Beispiel: Website Relaunch"
            required
            maxLength={120}
            autoFocus
          />
        </label>
        <label>
          Kürzel
          <input
            name="key"
            placeholder="WEB"
            required
            minLength={2}
            maxLength={12}
            pattern="[A-Za-z][A-Za-z0-9]{1,11}"
            style={{ textTransform: "uppercase" }}
          />
          <span className="tl-hint">
            Dauerhaftes Ticketkürzel, z. B. WEB-1.
          </span>
        </label>
        <label>
          Beschreibung
          <textarea
            name="description"
            placeholder="Worum geht es in diesem Projekt?"
            maxLength={10000}
            rows={3}
          />
        </label>
        <div className="tl-form-actions">
          <button className="tl-secondary" type="button" onClick={onClose}>
            Abbrechen
          </button>
          <button
            className="button"
            disabled={busy || !workspaces.some((w) => w.can_create_project)}
          >
            {busy ? "Erstellt …" : "Projekt erstellen"}
          </button>
        </div>
      </form>
    </WorkDialog>
  );
}
