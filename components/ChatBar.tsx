"use client";
// Type to her instead of talking.
import { useState } from "react";

export default function ChatBar({ onSend, disabled }: { onSend: (text: string) => void; disabled?: boolean }) {
  const [text, setText] = useState("");
  return (
    <form
      className="chatbar"
      onSubmit={(e) => {
        e.preventDefault();
        const t = text.trim();
        if (!t) return;
        setText("");
        onSend(t);
      }}
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type to Nemiii and press Enter…"
        aria-label="Type a message"
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
      />
      <button type="submit" disabled={disabled || !text.trim()}>SEND</button>
    </form>
  );
}
