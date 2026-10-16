"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import type { ChatResponse } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  text: string;
}

export function ChatWidget() {
  const { callApi } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hi! I'm the Aviator concierge. Ask me to find or book an empty seat." },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [sending, setSending] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const response = await callApi<ChatResponse>("/api/agent/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      setSessionId(response.session_id);
      setMessages((prev) => [...prev, { role: "assistant", text: response.reply || "..." }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Sorry, something went wrong: ${(err as Error).message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 rounded-full bg-aviator-sky px-5 py-3 font-semibold shadow-xl"
      >
        💬 Ask the concierge
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 flex h-[28rem] w-80 flex-col rounded-2xl border border-white/10 bg-aviator-midnight shadow-2xl">
      <div className="flex items-center justify-between border-b border-white/10 p-3">
        <span className="font-semibold">Aviator concierge</span>
        <button onClick={() => setOpen(false)} className="text-blue-100/60">
          ✕
        </button>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3 text-sm">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 ${
              m.role === "user" ? "ml-6 bg-aviator-sky" : "mr-6 bg-white/10"
            }`}
          >
            {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2 border-t border-white/10 p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Find me an economy seat to BOM..."
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm"
        />
        <button
          onClick={send}
          disabled={sending}
          className="rounded-lg bg-aviator-gold px-3 py-2 text-sm font-semibold text-aviator-midnight disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  );
}
