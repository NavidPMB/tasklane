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
  const hours = Math.floor(minutes / 60),
    rest = minutes % 60;
  return hours ? `${hours} h${rest ? ` ${rest} min` : ""}` : `${rest} min`;
}
export function localDate(date = new Date()) {
  return date.toLocaleDateString("sv-SE");
}
export function displayDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString("de-DE");
}
