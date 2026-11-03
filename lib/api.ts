// Every call to the Python backend lives here.
import type { CreationFile, ProgressInfo, StudioInfo, ActivityItem, ChatResponse, Dashboard, Health, PersonaInfo, ReminderItem } from "./types";

export const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export const timezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
};

async function post<T>(path: string, body: unknown, timeoutMs = 120000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(BACKEND + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`${path} returned ${r.status}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BACKEND + path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} returned ${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  chat: (message: string, lat?: number, lon?: number, persona?: string) =>
    post<ChatResponse>("/chat", { message, lat, lon, persona, tz: timezone() }),
  vision: (image: string, question: string) =>
    post<{ reply: string; provider: string; error?: string }>("/vision", { image, question }, 200000),
  gesture: (name: string) => post<{ ok: boolean; message: string }>("/gesture_action", { name }, 30000),
  resetMemory: (all = false) => post<{ ok: boolean }>("/reset_memory", { all }, 10000),
  setMode: (key: string) => post<PersonaInfo>("/mode", { key }, 10000),
  setTheme: (theme: string) => post<{ theme: string }>("/settings", { theme }, 10000),
  forgetFact: (keyword: string) => post<{ removed: number }>("/facts/forget", { keyword }, 10000),
  health: () => get<Health>("/health" + (timezone() ? `?tz=${encodeURIComponent(timezone()!)}` : "")),
  dashboard: (lat?: number, lon?: number) =>
    get<Dashboard>("/dashboard" + (lat !== undefined && lon !== undefined ? `?lat=${lat}&lon=${lon}` : "")),
  reminders: () => get<{ items: ReminderItem[] }>("/reminders"),
  remindersDue: () => get<{ due: { id: string; text: string }[] }>("/reminders/due"),
  deleteReminder: async (id: string) => {
    await fetch(`${BACKEND}/reminders/${id}`, { method: "DELETE" });
  },
  activity: () => get<{ items: ActivityItem[] }>("/activity?limit=40"),
  studio: () => get<StudioInfo>("/studio"),
  studioProgress: () => get<ProgressInfo>("/studio/progress"),
  studioFiles: (folder?: string) => get<{ items: CreationFile[]; problem: string | null }>("/studio/files" + (folder ? `?folder=${folder}` : "")),
  openCreation: (folder: string, name: string) => post<{ ok: boolean; message: string }>("/studio/open", { folder, name }, 20000),
  facts: () => get<{ facts: string[] }>("/facts"),
};

export const creationUrl = (c: { folder: string; name: string }) =>
  `${BACKEND}/studio/file/${encodeURIComponent(c.folder)}/${encodeURIComponent(c.name)}`;
