import "server-only";

import { cache } from "react";
import { notFound } from "next/navigation";
import { BackendError, backendFetch } from "@/lib/auth";

export type Visibility = "public" | "registered" | "internal";
export const visibilityLabels: Record<Visibility, string> = {
  public: "Öffentlich",
  registered: "Angemeldete Benutzer",
  internal: "Intern · nur Superuser",
};
export type WikiEntry = {
  id: number;
  title: string;
  slug: string;
  summary: string;
  visibility: Visibility;
  updatedAt: string;
};
export type WikiArticle = WikiEntry & { body: string };

export const getArticle = cache(async (slug: string) => {
  try {
    return await backendFetch<WikiArticle>(
      `/api/wiki/${encodeURIComponent(slug)}/`,
    );
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) notFound();
    throw error;
  }
});
