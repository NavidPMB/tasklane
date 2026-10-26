import "server-only";

import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type Session = {
  authenticated: boolean;
  csrfToken: string;
  googleLoginEnabled: boolean;
  user: {
    id: number;
    email: string;
    name: string;
    firstName: string;
    lastName: string;
    hasPassword: boolean;
    isStaff: boolean;
    isSuperuser: boolean;
  } | null;
};

export class BackendError extends Error {
  constructor(public status: number) {
    super(`Backend-Anfrage fehlgeschlagen: ${status}`);
  }
}

export async function backendFetch<T>(route: string): Promise<T> {
  const cookieStore = await cookies();
  const base = (process.env.BACKEND_URL || "http://127.0.0.1:8002").replace(
    /\/$/,
    "",
  );
  // Interne Server-Anfragen behalten die konfigurierte öffentliche HTTPS-Origin.
  const publicUrl = new URL(process.env.PUBLIC_URL || "http://localhost:3002");
  const response = await fetch(`${base}${route}`, {
    headers: {
      Cookie: cookieStore.toString(),
      "X-Forwarded-Host": publicUrl.host,
      "X-Forwarded-Proto": publicUrl.protocol.slice(0, -1),
    },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new BackendError(response.status);
  return response.json() as Promise<T>;
}

export const getSession = cache(() =>
  backendFetch<Session>("/api/auth/session/"),
);

export async function requireUser(staff = false) {
  const session = await getSession();
  if (!session.authenticated || !session.user) redirect("/login");
  if (staff && !session.user.isStaff)
    redirect("/dashboard?notice=staff-required");
  return session.user;
}
