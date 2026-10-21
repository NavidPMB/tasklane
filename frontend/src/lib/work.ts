export type Person = {
  id: number;
  name: string;
  email: string;
  inherited?: boolean;
};
export type Workspace = {
  id: number;
  name: string;
  owner_id: number;
  can_manage: boolean;
  can_create_project: boolean;
  project_count: number;
};
export type Project = {
  workspace_id: number;
  workspace_name: string;
  id: number;
  name: string;
  key: string;
  description: string;
  owner_id: number;
  can_manage: boolean;
  ticket_count: number;
};
export type Category = { id: string; name: string };
export type Status = {
  id: number;
  name: string;
  category: string;
  position: number;
  is_base: boolean;
};
export type Tag = { id: number; name: string };
export type Ticket = {
  id: number;
  key: string;
  project_id: number;
  title: string;
  description: string;
  kind: "epic" | "ticket";
  parent_id: number | null;
  status_id: number;
  assignee_ids: number[];
  tag_ids: number[];
  priority: string;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  jira: { key: string; url: string } | null;
  logged_minutes: number;
};
export type ProjectData = {
  project: Project;
  categories: Category[];
  statuses: Status[];
  members: Person[];
  tags: Tag[];
  tickets: Ticket[];
};
export const priorities: Record<string, string> = {
  low: "Niedrig",
  normal: "Normal",
  high: "Hoch",
  urgent: "Dringend",
};

export class WorkRequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function readResponse(response: Response) {
  if (response.status === 401) {
    window.location.assign("/login");
    throw new WorkRequestError("Bitte erneut anmelden.", 401);
  }
  const body = await response.json().catch(() => {
    throw new WorkRequestError(
      "Der Dienst ist gerade nicht erreichbar. Bitte erneut laden.",
      response.status,
    );
  });
  if (!response.ok)
    throw new WorkRequestError(
      body.error || "Anfrage fehlgeschlagen. Bitte erneut laden.",
      response.status,
    );
  return body;
}

export async function workFetch<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  const body = await readResponse(response);
  return body as T;
}

export async function workAction<T>(
  action: string,
  args: Record<string, unknown>,
): Promise<T> {
  const session = await workFetch<{ csrfToken: string }>("/api/auth/session/");
  const response = await fetch("/api/work/actions/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": session.csrfToken,
    },
    body: JSON.stringify({ action, arguments: args }),
  });
  const body = await readResponse(response);
  return body.result as T;
}
