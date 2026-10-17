"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import type { ChatResponse } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  text: string;
}

function renderInline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={index} className="font-semibold text-white">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={index}>{part}</span>
    )
  );
}

function renderAssistantMessage(text: string) {
  const lines = text.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("|")) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      const rows = tableLines
        .filter((row) => !/^\|?\s*:?-{3,}/.test(row))
        .map((row) => row.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
      const [headers, ...body] = rows;
      if (headers?.length) {
        blocks.push(
          <div key={`table-${index}`} className="my-2 overflow-x-auto rounded-lg border border-white/10">
            <table className="w-full min-w-[34rem] border-collapse text-left text-xs">
              <thead className="bg-white/[0.08] text-blue-100">
                <tr>
                  {headers.map((cell, cellIndex) => (
                    <th key={cellIndex} className="whitespace-nowrap px-2.5 py-2 font-semibold">
                      {renderInline(cell)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row, rowIndex) => (
                  <tr key={rowIndex} className="border-t border-white/[0.08]">
                    {headers.map((_, cellIndex) => (
                      <td key={cellIndex} className="whitespace-nowrap px-2.5 py-2 text-blue-50/90">
                        {renderInline(row[cellIndex] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }

    if (/^[-*]\s+/.test(line) || /^\d+[.)]\s+/.test(line)) {
      const ordered = /^\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (
        index < lines.length &&
        (ordered ? /^\s*\d+[.)]\s+/.test(lines[index]) : /^\s*[-*]\s+/.test(lines[index]))
      ) {
        items.push(lines[index].trim().replace(/^(?:[-*]|\d+[.)])\s+/, ""));
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List
          key={`list-${index}`}
          className={`my-1 space-y-1 pl-5 ${ordered ? "list-decimal" : "list-disc"}`}
        >
          {items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInline(item)}</li>
          ))}
        </List>
      );
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      blocks.push(
        <h3 key={`heading-${index}`} className="mb-1 mt-2 font-semibold text-white">
          {renderInline(heading[1])}
        </h3>
      );
      index += 1;
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(?:\||[-*]\s+|\d+[.)]\s+|#{1,3}\s)/.test(lines[index].trim())) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(
      <p key={`paragraph-${index}`} className="my-1 whitespace-pre-wrap">
        {renderInline(paragraph.join(" "))}
      </p>
    );
  }

  return <div className="space-y-1 leading-6">{blocks}</div>;
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
    <div className="fixed bottom-4 right-4 z-50 flex h-[min(34rem,calc(100vh-2rem))] w-[calc(100vw-2rem)] flex-col rounded-2xl border border-white/10 bg-aviator-midnight shadow-2xl sm:bottom-6 sm:right-6 sm:w-96">
      <div className="flex shrink-0 items-center justify-between border-b border-white/10 p-3">
        <span className="font-semibold">Aviator concierge</span>
        <button onClick={() => setOpen(false)} className="text-blue-100/60">
          ✕
        </button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 ${
              m.role === "user"
                ? "ml-6 bg-aviator-sky text-white"
                : "mr-2 max-w-full bg-white/10 text-blue-50"
            }`}
          >
            {m.role === "assistant" ? renderAssistantMessage(m.text) : m.text}
          </div>
        ))}
        {sending && (
          <div className="mr-10 rounded-lg bg-white/10 px-3 py-2 text-blue-100/60">
            Finding a helpful answer…
          </div>
        )}
      </div>
      <div className="flex shrink-0 gap-2 border-t border-white/10 p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about flights or memberships..."
          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm"
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
