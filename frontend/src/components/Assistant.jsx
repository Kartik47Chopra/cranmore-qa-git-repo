import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, docUrl } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Sparkles, X, Send, MapPin, FileText, ClipboardCheck, CornerDownLeft, Loader2 } from "lucide-react";

function renderMarkdown(text) {
  // minimal: **bold** and newlines
  const parts = [];
  let key = 0;
  for (const line of (text || "").split("\n")) {
    const chunks = line.split(/\*\*(.+?)\*\*/g);
    const rendered = chunks.map((c, i) => (i % 2 === 1 ? <strong key={i} className="font-semibold text-slate-900">{c}</strong> : c));
    parts.push(<div key={key++} className={line.startsWith("•") ? "pl-3" : ""}>{rendered.length ? rendered : <br />}</div>);
  }
  return parts;
}

const RESULT_ICON = { location: MapPin, document: FileText, visi: ClipboardCheck };
const RESULT_COLOR = { location: "text-emerald-600 bg-emerald-50", document: "text-sky-600 bg-sky-50", visi: "text-violet-600 bg-violet-50" };

export function Assistant({ open, onClose }) {
  const { projectId } = useProject();
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState([
    "What can you do?", "Where is the Main Kitchen?", "Room 101", "Find drawing A1203", "How many Visis are closed?",
  ]);
  const scrollRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open && messages.length === 0) {
      const first = (user?.name || "").split(" ")[0];
      setMessages([{ role: "bot", text: `Hey${first ? " " + first : ""}! 👋 I'm your site assistant. Ask me about any room, apartment, drawing or Visi — misspellings are fine, I'll figure it out.` }]);
    }
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, busy]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setBusy(true);
    try {
      const { data } = await api.post("/assistant/chat", { project_id: projectId, message: msg });
      setMessages((m) => [...m, { role: "bot", text: data.reply, results: data.results || [] }]);
      if (data.suggestions?.length) setSuggestions(data.suggestions);
    } catch {
      setMessages((m) => [...m, { role: "bot", text: "Something went wrong reaching the server — try again in a moment. In the meantime, you can browse the Locations tree on the left." }]);
    }
    setBusy(false);
  };

  const openResult = (r) => {
    if (r.type === "location") { navigate(`/location/${r.id}`); onClose?.(); }
    else if (r.type === "document") { window.open(docUrl(r.id), "_blank"); }
    else if (r.type === "visi") { navigate(`/location/${r.id}`); onClose?.(); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="w-full sm:w-[420px] h-full bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-200"
        onClick={(e) => e.stopPropagation()}
        data-testid="assistant-panel"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-200 bg-gradient-to-r from-emerald-600 to-teal-600 text-white shrink-0">
          <div className="h-9 w-9 rounded-xl bg-white/20 flex items-center justify-center">
            <Sparkles size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold leading-none">Site Assistant</div>
            <div className="text-[11px] text-emerald-100 mt-0.5">Knows every room, drawing & Visi</div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/15" data-testid="assistant-close">
            <X size={18} />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-slate-50">
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
              <div className={m.role === "user"
                ? "max-w-[85%] rounded-2xl rounded-br-md bg-emerald-600 text-white px-4 py-2.5 text-sm shadow-sm"
                : "max-w-[92%] rounded-2xl rounded-bl-md bg-white border border-slate-200 px-4 py-3 text-sm text-slate-700 shadow-sm space-y-2"}>
                {renderMarkdown(m.text)}
                {m.results?.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    {m.results.map((r) => {
                      const Icon = RESULT_ICON[r.type] || MapPin;
                      return (
                        <button
                          key={r.id}
                          onClick={() => openResult(r)}
                          data-testid={`assistant-result-${r.type}`}
                          className="w-full flex items-center gap-2.5 rounded-lg border border-slate-200 hover:border-emerald-400 hover:bg-emerald-50/50 px-3 py-2 text-left transition-colors group"
                        >
                          <span className={`h-7 w-7 rounded-lg flex items-center justify-center shrink-0 ${RESULT_COLOR[r.type] || ""}`}>
                            <Icon size={14} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-[13px] font-medium text-slate-800 truncate">{r.title}</span>
                            <span className="block text-[11px] text-slate-400 truncate">{r.subtitle}</span>
                          </span>
                          <CornerDownLeft size={13} className="text-slate-300 group-hover:text-emerald-500 shrink-0" />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-slate-400 text-sm px-1">
              <Loader2 size={14} className="animate-spin" /> Thinking…
            </div>
          )}
        </div>

        {/* Suggestions */}
        <div className="px-3 pb-2 shrink-0 bg-slate-50">
          <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => send(s)}
                className="shrink-0 text-[11px] font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-full px-3 py-1.5 transition-colors"
                data-testid={`assistant-suggestion-${i}`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="p-3 border-t border-slate-200 bg-white shrink-0">
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 focus-within:border-emerald-500 bg-slate-50 px-3 py-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask about a room, drawing, Visi…"
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400"
              data-testid="assistant-input"
            />
            <button
              onClick={() => send()}
              disabled={busy || !input.trim()}
              className="h-8 w-8 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white flex items-center justify-center transition-colors"
              data-testid="assistant-send"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AssistantButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      data-testid="assistant-fab"
      className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-600/30 hover:scale-105 active:scale-95 transition-transform px-4 py-3 font-semibold text-sm"
      aria-label="Open site assistant"
    >
      <Sparkles size={18} />
      <span className="hidden sm:inline">Ask AI</span>
    </button>
  );
}
