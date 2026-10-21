import { requireUser } from "@/lib/auth";
import { WorkspaceManager } from "@/components/work/workspace-manager";
export default async function WorkspacesPage({
  searchParams,
}: {
  searchParams: Promise<{ workspace?: string }>;
}) {
  await requireUser();
  const params = await searchParams;
  return (
    <WorkspaceManager
      initialWorkspace={Number(params.workspace) || undefined}
    />
  );
}
