export type AvatarState = "idle" | "listening" | "thinking" | "speaking";
export type Mode = "orb" | "video";

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
}
export interface Health {
  ok: boolean;
  version: string;
  user_name: string;
  local: { url: string | null; model: string; ready: boolean };
  groq_configured: boolean;
  pc_control_available: boolean;
  gmail_signed_in: boolean;
  saved_facts: number;
}
export interface Dashboard {
  place: string;
  weather: { temp_c: number; feels_c: number; humidity: number; wind_kmh: number; text: string } | null;
  news: { title: string; source: string }[];
  errors: string[];
}
