"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/ui/icon";
import { LogoutButton } from "@/components/auth/logout-button";
import { navigation, type Area } from "@/config/navigation";
import { project } from "@/config/project";
import type { Session } from "@/lib/auth";

export function WorkspaceShell({
  area,
  user,
  children,
}: {
  area: Area;
  user: NonNullable<Session["user"]>;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const section = navigation[area];
  const active = section.items.find((item) => item.href === pathname);

  return (
    <div className="workspace">
      <a className="skip-link" href="#workspace-content">
        Zum Inhalt springen
      </a>
      <aside className="primary-nav" aria-label="Hauptnavigation">
        <Link
          href="/"
          className="brand-mark"
          aria-label={`${project.name} Startseite`}
        >
          {project.monogram}
        </Link>
        <nav>
          <Link
            href="/dashboard"
            className={
              area === "dashboard" ? "rail-link selected" : "rail-link"
            }
            aria-label="Dashboard"
            title="Dashboard"
            aria-current={area === "dashboard" ? "page" : undefined}
          >
            <Icon name="grid" />
          </Link>
          {user.isStaff && (
            <Link
              href="/admin"
              className={area === "admin" ? "rail-link selected" : "rail-link"}
              aria-label="Admin"
              title="Admin"
              aria-current={area === "admin" ? "page" : undefined}
            >
              <Icon name="shield" />
            </Link>
          )}
          <Link
            href="/wiki"
            className="rail-link"
            aria-label="Wiki"
            title="Wiki"
          >
            <Icon name="book" />
          </Link>
          <Link
            href="/"
            className="rail-link"
            aria-label="Öffentliche Website"
            title="Öffentliche Website"
          >
            <Icon name="globe" />
          </Link>
        </nav>
        <Link
          href="/dashboard/account"
          className="avatar"
          title={user.name}
          aria-label="Mein Konto"
        >
          {user.name.charAt(0).toUpperCase()}
        </Link>
      </aside>
      {open && (
        <button
          className="nav-backdrop"
          aria-label="Menü schließen"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={`secondary-nav ${open ? "is-open" : ""}`}
        aria-label={`${section.label}-Navigation`}
      >
        <div className="section-brand">
          <span className="eyebrow">{project.name}</span>
          <strong>{section.label}</strong>
          <button
            className="mobile-close icon-button"
            aria-label="Menü schließen"
            onClick={() => setOpen(false)}
          >
            <Icon name="close" />
          </button>
        </div>
        <p className="nav-caption">{section.eyebrow}</p>
        <nav>
          {section.items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={`secondary-link ${pathname === item.href ? "active" : ""}`}
              aria-current={pathname === item.href ? "page" : undefined}
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="secondary-bottom">
          <span className="user-name">{user.name}</span>
          <span className="user-role">
            {user.isStaff ? "Administrator" : "Mitglied"}
          </span>
          <LogoutButton />
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-header">
          <div className="breadcrumb">
            <button
              className="mobile-toggle icon-button"
              aria-label="Bereichsmenü öffnen"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              <Icon name="menu" />
            </button>
            <span>{section.label}</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{active?.label || section.label}</strong>
          </div>
          <Link href="/" className="text-link">
            Zur Website <Icon name="arrow" width={15} height={15} />
          </Link>
        </header>
        <main id="workspace-content" className="workspace-content">
          {children}
        </main>
        <footer className="workspace-footer">
          {project.name}
          <span>Ein klarer Platz für deine Arbeit.</span>
        </footer>
      </div>
    </div>
  );
}
