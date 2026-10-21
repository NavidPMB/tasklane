import { PageHeading } from "@/components/ui/page-heading";
import { requireUser } from "@/lib/auth";

export default async function AccountPage() {
  const user = await requireUser();
  return (
    <>
      <PageHeading
        eyebrow="Persönlicher Bereich"
        title="Mein Konto"
        description="Deine Profildaten und dein Zugriff auf den Arbeitsbereich."
      />
      <section className="panel">
        <h2>Profil</h2>
        <dl className="detail-list">
          <div>
            <dt>Name</dt>
            <dd>{user.name}</dd>
          </div>
          <div>
            <dt>E-Mail-Adresse</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Rolle</dt>
            <dd>
              <span className="badge">
                {user.isStaff ? "Administrator" : "Mitglied"}
              </span>
            </dd>
          </div>
        </dl>
      </section>
    </>
  );
}
