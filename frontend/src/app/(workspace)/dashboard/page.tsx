import { TicketWorkspace } from "@/components/work/ticket-workspace";
import { requireUser } from "@/lib/auth";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{
    project?: string;
    ticket?: string;
    workspace?: string;
    notice?: string;
  }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  return (
    <>
      {params.notice === "staff-required" && (
        <p className="notice" role="status">
          Der Admin-Bereich ist für Administratoren vorgesehen.
        </p>
      )}
      <TicketWorkspace
        userId={user.id}
        initialWorkspace={Number(params.workspace) || undefined}
        initialProject={Number(params.project) || undefined}
        initialTicket={Number(params.ticket) || undefined}
      />
    </>
  );
}
