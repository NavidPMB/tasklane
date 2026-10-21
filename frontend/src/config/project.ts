// Beim Klonen hier Projektname und Farben ändern. Alle Bereiche verwenden diese Tokens.
export const project = {
  name: "Tasklane",
  monogram: "TL",
  description:
    "Dein gemeinsamer Arbeitsbereich für Tickets, Projekte und Teamarbeit.",
  colors: {
    primary: "#213d62",
    secondary: "#5177d1",
    background: "#f5f6f8",
    surface: "#ffffff",
    text: "#1c293a",
    muted: "#64748b",
    border: "#e2e7ee",
  },
} as const;

export const themeVariables = Object.fromEntries(
  Object.entries(project.colors).map(([name, value]) => [
    `--color-${name}`,
    value,
  ]),
);
