import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/icon";
import { project } from "@/config/project";
import { PublicHeader } from "@/components/layout/public-header";

const features: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "globe",
    title: "Ein guter erster Eindruck.",
    text: "Ein öffentlicher Ort für deine Ideen, dein Angebot und alles, was dein Projekt ausmacht.",
  },
  {
    icon: "grid",
    title: "Alles an einem Ort.",
    text: "Ein persönlicher Arbeitsbereich mit klarer Navigation und Platz für die nächsten Schritte.",
  },
  {
    icon: "shield",
    title: "Die Übersicht behalten.",
    text: "Ein eigener Bereich für die Verwaltung – zugänglich für berechtigte Teammitglieder.",
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <a className="skip-link" href="#main">
        Zum Inhalt springen
      </a>
      <PublicHeader />
      <main id="main">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="tiny-line" />
              Ein klarer Anfang.
            </p>
            <h1>
              Deine Ideen.
              <br />
              Ein gemeinsamer
              <br />
              <span>Arbeitsbereich.</span>
            </h1>
            <p className="hero-description">
              {project.description} Übersichtlich organisiert, einfach
              zugänglich und bereit, mit dir zu wachsen.
            </p>
            <div className="hero-actions">
              <Link href="/dashboard" className="button">
                Zum Arbeitsbereich <Icon name="arrow" width={17} height={17} />
              </Link>
              <a href="#bereiche" className="text-link">
                Mehr entdecken
              </a>
            </div>
            <p className="hero-note">
              <Icon name="check" width={15} height={15} />
              Mit deinem Google-Konto starten
            </p>
          </div>
          <div className="workspace-illustration" aria-hidden="true">
            <div className="illustration-title">
              <span className="mini-mark">{project.monogram}</span>
              <span>{project.name}</span>
              <span className="illustration-dots">···</span>
            </div>
            <div className="illustration-body">
              <div className="illustration-rail">
                <Icon name="grid" />
                <Icon name="layers" />
                <Icon name="shield" />
              </div>
              <div className="illustration-content">
                <span className="eyebrow">DEIN ARBEITSBEREICH</span>
                <h2>
                  Raum für das,
                  <br />
                  was als Nächstes kommt.
                </h2>
                <div className="illustration-cards">
                  <div>
                    <Icon name="globe" />
                    <span>Website</span>
                  </div>
                  <div>
                    <Icon name="grid" />
                    <span>Dashboard</span>
                  </div>
                  <div>
                    <Icon name="shield" />
                    <span>Admin</span>
                  </div>
                </div>
                <div className="illustration-line long" />
                <div className="illustration-line" />
                <div className="illustration-status">
                  <span /> Alles an seinem Platz
                </div>
              </div>
            </div>
          </div>
        </section>
        <section id="bereiche" className="feature-section">
          <div className="section-intro">
            <p className="eyebrow">Drei Bereiche. Eine Basis.</p>
            <h2>
              Von außen klar.
              <br />
              Von innen gut organisiert.
            </h2>
          </div>
          <div className="feature-grid">
            {features.map((feature, index) => (
              <article className="feature" key={feature.title}>
                <div className="feature-top">
                  <Icon name={feature.icon} />
                  <span>0{index + 1}</span>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <footer className="public-footer">
        <span>{project.name}</span>
        <span>Platz für deinen nächsten Schritt.</span>
        <Link href="/login">
          Zum Login <Icon name="arrow" width={15} height={15} />
        </Link>
      </footer>
    </div>
  );
}
