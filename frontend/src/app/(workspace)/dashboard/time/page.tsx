import { TimeReports } from "@/components/work/time-reports";
import { requireUser } from "@/lib/auth";

export default async function TimePage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string }>;
}) {
  await requireUser();
  const params = await searchParams;
  return <TimeReports initialProject={Number(params.project) || undefined} />;
}
