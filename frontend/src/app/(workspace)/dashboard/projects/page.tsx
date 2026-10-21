import { TicketWorkspace } from "@/components/work/ticket-workspace";
import { requireUser } from "@/lib/auth";
export default async function ProjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ workspace?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  return (
    <TicketWorkspace
      userId={user.id}
      initialView="projects"
      initialWorkspace={Number(params.workspace) || undefined}
    />
  );
}
