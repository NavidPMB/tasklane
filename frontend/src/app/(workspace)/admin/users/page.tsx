import Link from "next/link";
import { PageHeading } from "@/components/ui/page-heading";
import { backendFetch, requireUser } from "@/lib/auth";

type UserList = {
  count: number;
  page: number;
  results: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_active: boolean;
  }[];
};

export default async function UsersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  await requireUser(true);
  const params = await searchParams;
  const page = Math.max(1, Number.parseInt(params.page || "1", 10) || 1);
  const users = await backendFetch<UserList>(`/api/admin/users/?page=${page}`);
  return (
    <>
      <PageHeading
        eyebrow="Verwaltung"
        title="Benutzer"
        description={`${users.count} registrierte Konten in deinem Projekt.`}
      />
      <section className="panel table-panel">
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Registrierte Benutzer</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">E-Mail-Adresse</th>
                <th scope="col">Rolle</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.results.map((user) => (
                <tr key={user.id}>
                  <td>
                    {[user.first_name, user.last_name]
                      .filter(Boolean)
                      .join(" ") || "–"}
                  </td>
                  <td>{user.email}</td>
                  <td>{user.is_staff ? "Administrator" : "Mitglied"}</td>
                  <td>
                    <span className="badge">
                      {user.is_active ? "Aktiv" : "Deaktiviert"}
                    </span>
                  </td>
                </tr>
              ))}
              {users.results.length === 0 && (
                <tr>
                  <td colSpan={4}>Keine Benutzer auf dieser Seite.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <nav className="pagination" aria-label="Benutzerseiten">
          {page > 1 && (
            <Link href={`/admin/users?page=${page - 1}`}>← Zurück</Link>
          )}
          <span>Seite {page}</span>
          {page * 50 < users.count && (
            <Link href={`/admin/users?page=${page + 1}`}>Weiter →</Link>
          )}
        </nav>
      </section>
    </>
  );
}
