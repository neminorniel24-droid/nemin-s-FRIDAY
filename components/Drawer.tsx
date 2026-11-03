"use client";
// The side panel: CHAT history, REMINDERS, ACTIVITY (everything she did) and MEMORY (what she remembers).
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActivityItem, ChatLine, ReminderItem, StudioInfo } from "@/lib/types";

export type Tab = "chat" | "reminders" | "activity" | "memory" | "studio";
const TABS: Tab[] = ["chat", "reminders", "activity", "studio", "memory"];

interface Props {
  open: boolean;
  tab: Tab;
  setTab: (t: Tab) => void;
  lines: ChatLine[];
  online: boolean;
  onClose: () => void;
}

export default function Drawer({ open, tab, setTab, lines, online, onClose }: Props) {
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [facts, setFacts] = useState<string[]>([]);
  const [studio, setStudio] = useState<StudioInfo | null>(null);

  const refresh = useCallback(async () => {
    if (!online) return;
    try {
      if (tab === "reminders") setReminders((await api.reminders()).items);
      else if (tab === "activity") setActivity((await api.activity()).items);
      else if (tab === "studio") setStudio(await api.studio());
      else if (tab === "memory") setFacts((await api.facts()).facts);
    } catch {
      /* backend busy: try again on the next tick */
    }
  }, [tab, online]);

  useEffect(() => {
    if (!open) return;
    void refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [open, refresh]);

  useEffect(() => {
    // keep the newest chat line in view
    if (open && tab === "chat") document.getElementById("chat-end")?.scrollIntoView({ block: "end" });
  }, [open, tab, lines.length]);

  if (!open) return null;
  return (
    <aside className="drawer panel">
      <div className="drawer-head">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t.toUpperCase()}</button>
        ))}
        <button className="x" onClick={onClose} aria-label="Close panel">×</button>
      </div>

      <div className="drawer-body">
        {tab === "chat" && (
          <>
            {lines.length === 0 && <div className="dim">Nothing yet. Say something or type below.</div>}
            {lines.map((l) => (
              <div key={l.id} className={`line ${l.role}`}>
                <span className="who">{l.role === "you" ? "YOU" : l.role === "her" ? "HER" : "·"}</span> {l.text}
              </div>
            ))}
            <div id="chat-end" />
          </>
        )}

        {tab === "reminders" && (
          reminders.length === 0 ? <div className="dim">No reminders. Say “remind me in 20 minutes to stretch”.</div> :
            reminders.map((r) => (
              <div key={r.id} className="line">
                {r.pretty}
                <button className="mini-x" title="Delete" onClick={async () => { await api.deleteReminder(r.id); void refresh(); }}>×</button>
              </div>
            ))
        )}

        {tab === "activity" && (
          activity.length === 0 ? <div className="dim">She hasn’t done anything yet.</div> :
            activity.map((a, i) => (
              <div key={i} className={`line ${a.ok ? "" : "bad"}`}>
                <span className="who">{a.at.slice(11, 16)}</span> {a.action.replace(/_/g, " ")}
                <span className="dim"> · {a.ok ? "ok" : "failed"} · {a.message}</span>
              </div>
            ))
        )}

        {tab === "studio" && (
          !studio ? <div className="dim">Loading…</div> : (
            <>
              <div className={`line ${studio.problem ? "bad" : ""}`}>
                {studio.problem ?? `SSD folder ${studio.root} · ${studio.free_gb} GB free`}
              </div>
              {studio.models.map((m) => (
                <div key={m.id} className="line">
                  <span className="who">{m.installed ? "ON" : m.job?.state === "running" ? `${m.job.pct}%` : "—"}</span> {m.name}
                  <span className="dim"> · {m.kind} · {m.gb} GB{m.tier === "experimental" || m.tier === "isolated" ? ` · ${m.tier}` : ""}</span>
                </div>
              ))}
              <div className="dim">Say “install the image model” or “make music, calm piano”.</div>
            </>
          )
        )}

        {tab === "memory" && (
          facts.length === 0 ? <div className="dim">Nothing saved. Say “remember that my exam is on Friday”.</div> :
            facts.map((f, i) => (
              <div key={i} className="line">
                {f}
                <button className="mini-x" title="Forget" onClick={async () => { await api.forgetFact(f); void refresh(); }}>×</button>
              </div>
            ))
        )}
      </div>
    </aside>
  );
}
