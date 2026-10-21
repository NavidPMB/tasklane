import Link from "next/link";
import { PageHeading } from "@/components/ui/page-heading";
import { Icon } from "@/components/ui/icon";
import { backendFetch, requireUser } from "@/lib/auth";

export default async function AdminPage() {
  await requireUser(true);
  const overview = await backendFetch<{ users: number; staff: number }>(
    "/api/admin/",
  );
  return (
    <>
      <PageHeading
        eyebrow="Verwaltung"
        title="Alles im Überblick."
        description="Verwalte den Zugang zu deinem Projekt."
      />
      <div className="stats-grid">
        <section className="stat-card">
          <span>Benutzer insgesamt</span>
          <strong>{overview.users}</strong>
          <Icon name="users" />
        </section>
        <section className="stat-card">
          <span>Administratoren</span>
          <strong>{overview.staff}</strong>
          <Icon name="shield" />
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Benutzer & Zugänge</h2>
            <p>Alle registrierten Konten an einem Ort.</p>
          </div>
          <Link href="/admin/users" className="button button-small">
            Benutzer ansehen <Icon name="arrow" width={16} height={16} />
          </Link>
        </div>
      </section>
    </>
  );
}
