import { WorkspaceShell } from "@/components/shell/workspace-shell";
import { requireUser } from "@/lib/auth";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser(true);
  return (
    <WorkspaceShell area="admin" user={user}>
      {children}
    </WorkspaceShell>
  );
}
