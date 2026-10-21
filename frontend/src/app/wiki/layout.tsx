import { PublicHeader } from "@/components/layout/public-header";
import { project } from "@/config/project";
import { getSession } from "@/lib/auth";
import "./wiki.css";

export default async function WikiLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  return (
    <div className="wiki-site">
      <a className="skip-link" href="#wiki-content">
        Zum Inhalt springen
      </a>
      <PublicHeader wiki authenticated={session.authenticated} />
      {children}
      <footer className="public-footer wiki-footer">
        <span>{project.name}</span>
        <span>Wissen an einem Ort.</span>
        <a href="/">Zur Website</a>
      </footer>
    </div>
  );
}
