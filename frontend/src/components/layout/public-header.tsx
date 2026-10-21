import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { project } from "@/config/project";

export function PublicHeader({
  wiki = false,
  authenticated = false,
}: {
  wiki?: boolean;
  authenticated?: boolean;
}) {
  return (
    <header className="public-header">
      <Link href="/" className="wordmark">
        <span className="brand-mark">{project.monogram}</span>
        {project.name}
      </Link>
      <nav aria-label="Seitennavigation">
        <a href="/#bereiche" className="text-link discover-link">
          Entdecken
        </a>
        <Link
          href="/wiki"
          className="text-link wiki-header-link"
          aria-current={wiki ? "page" : undefined}
        >
          Wiki
        </Link>
        <Link
          href={authenticated ? "/dashboard" : "/login"}
          className="button button-small"
        >
          {authenticated ? "Arbeitsbereich" : "Anmelden"}{" "}
          <Icon name="arrow" width={16} height={16} />
        </Link>
      </nav>
    </header>
  );
}
