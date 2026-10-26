import { requireUser } from "@/lib/auth";
import { IntegrationAccess } from "@/components/work/integration-access";
export default async function McpPage() {
  await requireUser();
  return (
    <IntegrationAccess
      publicUrl={(process.env.PUBLIC_URL || "http://localhost:3010").replace(
        /\/$/,
        "",
      )}
    />
  );
}
