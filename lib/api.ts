// Every call to the Python backend lives here.
import type { ChatResponse, Dashboard, Health } from "./types";

export const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

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

export const api = {
  chat: (message: string, lat?: number, lon?: number) => post<ChatResponse>("/chat", { message, lat, lon }),
  vision: (image: string, question: string) =>
    post<{ reply: string; provider: string; error?: string }>("/vision", { image, question }, 200000),
  gesture: (name: string) => post<{ ok: boolean; message: string }>("/gesture_action", { name }, 30000),
  resetMemory: (all = false) => post<{ ok: boolean }>("/reset_memory", { all }, 10000),
  async health(): Promise<Health> {
    const r = await fetch(BACKEND + "/health", { cache: "no-store" });
    return r.json();
  },
  async dashboard(lat?: number, lon?: number): Promise<Dashboard> {
    const q = lat !== undefined && lon !== undefined ? `?lat=${lat}&lon=${lon}` : "";
    const r = await fetch(BACKEND + "/dashboard" + q, { cache: "no-store" });
    return r.json();
  },
};
