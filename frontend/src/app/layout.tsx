import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { project, themeVariables } from "@/config/project";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: project.name, template: `%s · ${project.name}` },
  description: project.description,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de" style={themeVariables as CSSProperties}>
      <body>{children}</body>
    </html>
  );
}
