import path from "node:path";
import { requireUser } from "@/lib/auth";
import { PageHeading } from "@/components/ui/page-heading";
import { Icon } from "@/components/ui/icon";

export default async function McpPage() {
  const user = await requireUser();
  const root = path.resolve(process.cwd(), "..");
  const config = {
    mcpServers: {
      tasklane: {
        command: path.join(root, ".venv/bin/python"),
        args: [path.join(root, "backend/mcp_server.py")],
        env: { TASKLANE_MCP_USER_EMAIL: user.email },
      },
    },
  };
  return (
    <div className="tl-mcp-page">
      <PageHeading
        eyebrow="MCP-Anbindung"
        title="Deine Tickets. Direkt im Assistenten."
        description="Verbinde einen lokalen MCP-Client mit deinem Tasklane-Konto."
      />
      <div className="tl-mcp-banner">
        <span className="tl-empty-icon">
          <Icon name="terminal" width={28} height={28} />
        </span>
        <div>
          <h2>Ein Workflow für Board und Assistent</h2>
          <p>
            Der MCP-Server arbeitet mit denselben Projekten, Tickets und
            Berechtigungen wie die Oberfläche. Neue Status sind direkt über die
            Werkzeuge verfügbar.
          </p>
        </div>
      </div>
      <section className="tl-mcp-section">
        <h2>1. Lokalen MCP-Client verbinden</h2>
        <p>
          Trage diese Konfiguration in einen MCP-Client mit stdio-Unterstützung
          ein. Der Client startet den Server automatisch; PostgreSQL muss
          laufen. Die Konfiguration verwendet dein bestehendes Konto.
        </p>
        <pre>
          <code>{JSON.stringify(config, null, 2)}</code>
        </pre>
        <p className="tl-hint">
          Diese Verbindung läuft auf demselben Rechner wie Tasklane. Sie
          benötigt keinen zusätzlichen Port und keinen Browser-Token.
        </p>
      </section>
      <section className="tl-mcp-section">
        <h2>2. Mit deinen Projekten arbeiten</h2>
        <div className="tl-prompt-examples">
          <p>
            „Erstelle einen Workspace GroupFractal und zeige seine Projekte.“
          </p>
          <p>„Zeige meine Projekte und die offenen Tickets.“</p>
          <p>
            „Suche Jira-Tickets im Workspace GroupFractal und importiere WEB-1
            und WEB-2.“
          </p>
          <p>
            „Erstelle im Projekt WEB ein Epic für den Relaunch und drei
            Untertickets.“
          </p>
          <p>
            „Füge nach In Arbeit den Status Review ein und verschiebe WEB-3
            dorthin.“
          </p>
          <p>
            „Weise WEB-3 einem Projektmitglied zu und setze den Tag Frontend.“
          </p>
          <p>
            „Prüfe abgeschlossene ClickUp-Aufgaben mit ihrer gesamten
            Zeithistorie, importiere sie und zeige den historischen Bericht pro
            Person.“
          </p>
          <p>„Buche heute 90 Minuten Entwicklung auf WEB-3.“</p>
          <p>
            „Zeige die gebuchte Arbeitszeit dieses Monats pro Person und
            Projekt.“
          </p>
        </div>
      </section>
      <section className="tl-mcp-section">
        <h2>Verfügbare Werkzeuge</h2>
        <div className="tl-mcp-tools">
          <div>
            <strong>Workspaces & Jira</strong>
            <p>
              Workspaces erstellen, mit bestehenden Konten teilen und Projekte
              darin verwalten. Jira-Verbindung prüfen, Tickets per JQL suchen
              und ausgewählt importieren. Zugangsdaten vorzugsweise im
              Jira-Panel hinterlegen.
            </p>
          </div>
          <div>
            <strong>ClickUp & Zeithistorie</strong>
            <p>
              Aufgaben auswählen, sämtliche historischen Zeitbuchungen prüfen
              und den geprüften Stand übernehmen. Frühere Mitwirkende, exakte
              Dauer und abgeschlossene Aufgaben bleiben auswertbar.
            </p>
          </div>
          <div>
            <strong>Projekte & Team</strong>
            <p>
              Projekte auflisten, erstellen und bearbeiten. Mitglieder
              hinzufügen oder entfernen.
            </p>
          </div>
          <div>
            <strong>Tickets & Epics</strong>
            <p>
              Suchen, lesen, erstellen, bearbeiten, zuweisen, taggen und
              Untertickets verknüpfen.
            </p>
          </div>
          <div>
            <strong>Dynamischer Workflow</strong>
            <p>
              Status lesen, ergänzen, umsortieren und mit Ersatzstatus
              entfernen. Tags verwalten.
            </p>
          </div>
          <div>
            <strong>Zeiterfassung & Berichte</strong>
            <p>
              Eigene Arbeitszeit buchen und korrigieren. Zeiten nach Person,
              Projekt und Zeitraum auswerten oder als CSV exportieren.
            </p>
          </div>
        </div>
        <p className="tl-hint">
          Status- und Mitglieder-IDs werden aus dem jeweiligen Projekt gelesen.
          Der Assistent greift ausschließlich auf Projekte dieses Kontos zu. Das
          Board übernimmt MCP-Änderungen spätestens bei der nächsten
          automatischen Aktualisierung.
        </p>
      </section>
    </div>
  );
}
