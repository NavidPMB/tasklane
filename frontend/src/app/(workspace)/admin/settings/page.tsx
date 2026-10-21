import { PageHeading } from "@/components/ui/page-heading";
import { Icon } from "@/components/ui/icon";
import { requireUser } from "@/lib/auth";

export default async function SettingsPage() {
  await requireUser(true);
  return (
    <>
      <PageHeading
        eyebrow="Verwaltung"
        title="Einstellungen"
        description="Integrationen und Zugangsdaten für dein Projekt."
      />
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Integrationen & Zugangsdaten</h2>
            <p>
              Google Login, API-Schlüssel und MCP-Zugänge zentral einrichten.
              Für die Verwaltung ist ein Superuser-Konto erforderlich.
            </p>
          </div>
          <a
            href="/django-admin/integrations/integrationcredential/"
            className="button button-small"
          >
            Einstellungen öffnen <Icon name="arrow" width={16} height={16} />
          </a>
        </div>
      </section>
    </>
  );
}
