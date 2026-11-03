export type AvatarState = "idle" | "listening" | "thinking" | "speaking";
export type Mode = "orb" | "video";

export interface PersonaInfo {
  key: string;
  label: string;
  rate: number;
  pitch: number;
  greeting: string;
  prefer_voice: string;
  names: string[];
}
export interface ActionResult {
  name: string;
  kind: string;
  ok: boolean;
  message: string;
}
export interface ChatResponse {
  reply: string;
  actions: ActionResult[];
  provider: string;
  error?: string;
  ui?: { theme?: string; persona?: PersonaInfo; gallery?: boolean };
  confirm?: boolean;
  persona?: PersonaInfo;
}
export interface Health {
  ok: boolean;
  version: string;
  user_name: string;
  address_as: string;
  local: { url: string | null; model: string; ready: boolean };
  groq_configured: boolean;
  pc_control_available: boolean;
  tts_natural?: boolean;
  gmail_signed_in: boolean;
  home_assistant_configured: boolean;
  saved_facts: number;
  reminders: number;
  persona: PersonaInfo;
  personas: PersonaInfo[];
  wake_names: string[];
  theme: string;
  plugins: string[];
  actions: string[];
}
export interface Dashboard {
  place: string;
  weather: { temp_c: number; feels_c: number; humidity: number; wind_kmh: number; text: string } | null;
  news: { title: string; source: string }[];
  errors: string[];
}
export interface ReminderItem {
  id: string;
  text: string;
  pretty: string;
}
export interface ActivityItem {
  at: string;
  source: string;
  action: string;
  ok: boolean;
  message: string;
}
export interface ChatLine {
  id: number;
  role: "you" | "her" | "system";
  text: string;
  at: number;
}

export interface StudioModel {
  id: string; kind: string; name: string; gb: number; tier: string; how: string;
  installed: boolean; note: string; job: { state: string; message: string; pct: number } | null;
}
export interface StudioInfo { root: string | null; problem: string | null; free_gb: number | null; models: StudioModel[]; summary: string }

export interface CreationFile { folder: string; name: string; mtime: number; size: number }
export interface ProgressInfo {
  busy: boolean; started_at: number; kind: string; what: string; pct: number; stage: string; elapsed: number; error: string;
  latest: { folder: string; name: string } | null; recent: string[];
}
