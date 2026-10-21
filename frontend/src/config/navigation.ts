import type { IconName } from "@/components/ui/icon";

export type Area = "dashboard" | "admin";
type NavigationItem = { href: string; label: string; icon: IconName };

// Neue Module hier an die gemeinsame Secondary-Navigation hängen.
export const navigation: Record<
  Area,
  { label: string; eyebrow: string; items: NavigationItem[] }
> = {
  dashboard: {
    label: "Dashboard",
    eyebrow: "Dein Arbeitsbereich",
    items: [
      { href: "/dashboard", label: "Board & Tickets", icon: "board" },
      {
        href: "/dashboard/workspaces",
        label: "Workspaces & Team",
        icon: "users",
      },
      { href: "/dashboard/jira", label: "Jira-Import", icon: "arrow" },
      { href: "/dashboard/projects", label: "Projekte", icon: "layers" },
      { href: "/dashboard/time", label: "Zeiten & Berichte", icon: "clock" },
      { href: "/dashboard/mcp", label: "MCP-Anbindung", icon: "terminal" },
      { href: "/dashboard/account", label: "Mein Konto", icon: "user" },
    ],
  },
  admin: {
    label: "Admin",
    eyebrow: "Verwaltung",
    items: [
      { href: "/admin", label: "Übersicht", icon: "grid" },
      { href: "/admin/users", label: "Benutzer", icon: "users" },
      { href: "/admin/settings", label: "Einstellungen", icon: "layers" },
    ],
  },
};
