"use client";
// Two things: the progress bar while she makes something, and the viewer for everything she made.
// Files come from the backend (which only serves the four output folders on your SSD).
import { useCallback, useEffect, useState } from "react";
import { api, creationUrl } from "@/lib/api";
import type { CreationFile, ProgressInfo } from "@/lib/types";

interface Props {
  open: boolean;
  making: boolean;
  online: boolean;
  onClose: () => void;
  onMadeDone: (ok: boolean, info: string) => void;
}

const KIND_LABEL: Record<string, string> = { images: "PICTURE", music: "MUSIC", speech: "VOICE", transcripts: "TRANSCRIPT" };

export default function Creations({ open, making, online, onClose, onMadeDone }: Props) {
  const [progress, setProgress] = useState<ProgressInfo | null>(null);
  const [items, setItems] = useState<CreationFile[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [text, setText] = useState("");

  const loadItems = useCallback(async () => {
    try {
      const r = await api.studioFiles();
      setItems(r.items);
      setProblem(r.problem);
    } catch {
      /* backend busy */
    }
  }, []);

  // While something is being made: ask the backend how far along it is (right away, then every second).
  // The job is started before the action replies, so the backend always describes THIS job.
  useEffect(() => {
    if (!making || !online) return;
    let stopped = false;
    let empty = 0;
    const tick = async () => {
      try {
        const p = await api.studioProgress();
        if (stopped) return;
        setProgress(p);
        if (p.busy) return;
        if (!p.started_at && ++empty < 4) return;       // no job known yet, give it a moment
        stopped = true;
        clearInterval(id);
        setProgress(null);
        if (p.latest && !p.error) {
          await loadItems();
          setIndex(0);
          onMadeDone(true, p.latest.name);
        } else onMadeDone(false, p.error);
      } catch {
        /* try again next tick */
      }
    };
    const id = setInterval(tick, 1000);
    void tick();
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [making, online, loadItems, onMadeDone]);

  // Reload the list every time the viewer opens.
  useEffect(() => {
    if (open && online) void loadItems();
  }, [open, online, loadItems]);

  const current = items[index];
  useEffect(() => {
    setText("");
    if (current?.folder === "transcripts") {
      fetch(creationUrl(current)).then((r) => r.text()).then(setText).catch(() => setText("Could not read this file."));
    }
  }, [current?.folder, current?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {making && progress?.busy && (
        <div className="makebar panel">
          <div className="makebar-top">
            <span>MAKING · {progress.what.toUpperCase()}</span>
            <span>{progress.pct}%</span>
          </div>
          <div className="bar"><i style={{ width: `${progress.pct}%` }} /></div>
          <div className="makebar-sub">{progress.stage} · {progress.elapsed}s</div>
        </div>
      )}

      {open && (
        <div className="viewer panel">
          <div className="viewer-head">
            <span>CREATIONS {items.length ? `· ${index + 1} / ${items.length}` : ""}</span>
            <div>
              <button disabled={index >= items.length - 1} onClick={() => setIndex((i) => i + 1)}>◀ OLDER</button>
              <button disabled={index <= 0} onClick={() => setIndex((i) => i - 1)}>NEWER ▶</button>
              {current && <button onClick={() => void api.openCreation(current.folder, current.name)}>OPEN IN WINDOWS</button>}
              <button className="x" onClick={onClose} aria-label="Close">×</button>
            </div>
          </div>

          {!current && <div className="dim viewer-empty">{problem ?? "Nothing yet. Say “draw a neon city at night” or “make some calm piano”."}</div>}

          {current && (
            <div className="viewer-body">
              <div className="viewer-name">{KIND_LABEL[current.folder] ?? current.folder.toUpperCase()} · {current.name}</div>
              {current.folder === "images" && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={creationUrl(current)} alt={current.name} />
              )}
              {(current.folder === "music" || current.folder === "speech") && (
                <audio key={current.name} controls src={creationUrl(current)} />
              )}
              {current.folder === "transcripts" && <pre>{text || "Loading…"}</pre>}
            </div>
          )}

          {items.length > 1 && (
            <div className="viewer-strip">
              {items.slice(0, 24).map((it, i) => (
                <button key={it.folder + it.name} className={i === index ? "on" : ""} onClick={() => setIndex(i)} title={it.name}>
                  {it.folder === "images" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={creationUrl(it)} alt="" loading="lazy" />
                  ) : (
                    <span>{KIND_LABEL[it.folder]?.slice(0, 5) ?? "FILE"}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
