import { requireUser } from "@/lib/auth";
import { ClickUpImport } from "@/components/work/clickup-import";
export default async function ClickUpPage({
  searchParams,
}: {
  searchParams: Promise<{ workspace?: string }>;
}) {
  await requireUser();
  const params = await searchParams;
  return (
    <ClickUpImport initialWorkspace={Number(params.workspace) || undefined} />
  );
}
