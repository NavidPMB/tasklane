import { TimeReports } from "@/components/work/time-reports";
import { requireUser } from "@/lib/auth";

export default async function TimePage({
  searchParams,
}: {
  searchParams: Promise<{
    project?: string;
    workspace?: string;
    date_from?: string;
    date_to?: string;
  }>;
}) {
  await requireUser();
  const params = await searchParams;
  return (
    <TimeReports
      initialProject={Number(params.project) || undefined}
      initialWorkspace={Number(params.workspace) || undefined}
      initialFrom={params.date_from}
      initialTo={params.date_to}
    />
  );
}
