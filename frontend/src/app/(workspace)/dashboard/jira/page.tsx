import { requireUser } from "@/lib/auth";
import { JiraImport } from "@/components/work/jira-import";
export default async function JiraPage({
  searchParams,
}: {
  searchParams: Promise<{ workspace?: string }>;
}) {
  await requireUser();
  const params = await searchParams;
  return (
    <JiraImport initialWorkspace={Number(params.workspace) || undefined} />
  );
}
