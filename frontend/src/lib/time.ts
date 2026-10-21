import type { Person } from "./work";

export type TimeEntry = {
  id: number;
  project_id: number;
  project_name: string;
  ticket_id: number;
  ticket_key: string;
  ticket_title: string;
  user: Person;
  work_date: string;
  minutes: number;
  duration_ms: number;
  source: { provider: "clickup"; id: string; person: string } | null;
  note: string;
  can_edit: boolean;
  updated_at: string;
};
export type TimeEntries = {
  entries: TimeEntry[];
  total: number;
  total_minutes: number;
  offset: number;
  limit: number;
};
export type TimePerson = Person & { is_active: boolean };
export type TimeReport = {
  total_minutes: number;
  entry_count: number;
  ticket_count: number;
  people_count: number;
  date_from: string;
  date_to: string;
  people: TimePerson[];
  users: (TimePerson & {
    minutes: number;
    entry_count: number;
    ticket_count: number;
    day_count: number;
  })[];
  projects: { id: number; name: string; key: string; minutes: number }[];
  tickets: {
    id: number;
    key: string;
    title: string;
    project_id: number;
    minutes: number;
  }[];
  days: { date: string; minutes: number }[];
};
export function formatMinutes(minutes: number) {
  const totalMs = Math.round(minutes * 60000);
  const hours = Math.floor(totalMs / 3600000);
  const mins = Math.floor((totalMs % 3600000) / 60000);
  const seconds = (totalMs % 60000) / 1000;
  const parts = [
    hours ? `${hours} h` : "",
    mins ? `${mins} min` : "",
    seconds
      ? `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 3 }).format(seconds)} s`
      : "",
  ].filter(Boolean);
  return parts.join(" ") || "0 min";
}
export function localDate(date = new Date()) {
  return date.toLocaleDateString("sv-SE");
}
export function displayDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString("de-DE");
}
