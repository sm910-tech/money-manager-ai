import React, { useState } from "react";
import { Bot, Send, Sparkles, Lock } from "lucide-react";
import { sendChatMessage } from "../services/api";

const STARTER_PROMPTS = [
  "Where did most of my spending go this month?",
  "Which budgets am I close to exceeding?",
  "What recurring expenses can I optimize?",
];

export default function AiAssistantPanel({ isAuthenticated, selectedMonth }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Ask me anything about your spending patterns, budget utilization, or recurring bills. Every number comes directly from your backend Python analytics engine.",
      meta: "gemini-4-hydrogen",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (promptText) => {
    const question = (promptText ?? input).trim();
    if (!question || loading) return;

    if (!isAuthenticated) {
      setMessages((prev) => [
        ...prev,
        { role: "user", text: question },
        {
          role: "assistant",
          text: "Sign in with Google to ask natural-language questions against your private Firestore ledger via Gemini.",
          meta: "authentication-required",
        },
      ]);
      setInput("");
      return;
    }

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendChatMessage(question, selectedMonth);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.reply,
          meta: res.ai_available ? res.model_used : `${res.model_used} (AI unavailable)`,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Could not reach the AI assistant: ${err.message}`,
          meta: "error",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5 flex flex-col h-[560px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-emerald-500/15 text-emerald-400">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">AI Finance Copilot</h2>
            <p className="text-[11px] text-slate-400">
              Grounded in Python Decimal metrics • Gemini 4 Hydrogen
            </p>
          </div>
        </div>
        <Sparkles className="h-4 w-4 text-emerald-400" />
      </div>

      {!isAuthenticated && (
        <div className="mb-3 rounded-xl bg-slate-950 border border-slate-800 p-2.5 text-[11px] text-slate-400 flex items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-amber-400 shrink-0" />
          <span>Sign in with Google to activate live authenticated Gemini conversations.</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-line ${
                m.role === "user"
                  ? "bg-emerald-500 text-slate-950 font-medium"
                  : "bg-slate-800/90 text-slate-100 border border-slate-700/70"
              }`}
            >
              {m.text}
            </div>
            {m.role === "assistant" && m.meta && (
              <span className="text-[10px] text-slate-500 mt-1 px-1">Source: {m.meta}</span>
            )}
          </div>
        ))}
        {loading && (
          <div className="text-xs text-slate-400 animate-pulse px-2">
            Verifying metrics in Python &amp; consulting Gemini...
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 my-3">
        {STARTER_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => handleSend(prompt)}
            disabled={loading}
            className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about spending, budgets, or savings..."
          className="flex-1 rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 px-3.5 py-2 font-semibold disabled:opacity-40"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
