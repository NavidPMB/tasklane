import { TicketWorkspace } from "@/components/work/ticket-workspace";
import { requireUser } from "@/lib/auth";

export default async function ProjectsPage() {
  const user = await requireUser();
  return <TicketWorkspace userId={user.id} initialView="projects" />;
}
