import { WorkspaceShell } from "@/components/shell/workspace-shell";
import { requireUser } from "@/lib/auth";
import "@/components/work/work.css";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  return (
    <WorkspaceShell area="dashboard" user={user}>
      {children}
    </WorkspaceShell>
  );
}
