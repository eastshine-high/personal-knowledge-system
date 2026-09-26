import { useEffect, useRef, useState } from "react";
import { getMessages, sendMessage, ApiError } from "../api";
import type { Conversation, LLMUsage, Message } from "../types";

interface Props {
  conversation: Conversation;
}

function fmtCost(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.0001) return `~$${usd.toExponential(1)}`;
  return `~$${usd.toFixed(4)}`;
}

function fmtNum(n: number): string {
  return n.toLocaleString();
}

function UsageBadge({ usage }: { usage: LLMUsage }) {
  return (
    <div style={s.usageBadge}>
      <span style={s.usageModel}>{usage.model}</span>
      <span style={s.usageSep}>·</span>
      <span>↑{fmtNum(usage.input_tokens)} ↓{fmtNum(usage.output_tokens)}</span>
      {usage.cost_usd != null && (
        <>
          <span style={s.usageSep}>·</span>
          <span>{fmtCost(usage.cost_usd)}</span>
        </>
      )}
    </div>
  );
}

export default function ChatPanel({ conversation }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [usageMap, setUsageMap] = useState<Record<string, LLMUsage>>({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMessages(conversation.id).then(setMessages).catch(() => {});
    setUsageMap({});
  }, [conversation.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const submit = async () => {
    const content = input.trim();
    if (!content || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    const optimistic: Message = {
      id: `opt-${Date.now()}`, conversation_id: conversation.id,
      role: "user", content, created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    try {
      const resp = await sendMessage(conversation.id, content);
      setMessages((prev) => [...prev, resp.message]);
      if (resp.usage) {
        setUsageMap((prev) => ({ ...prev, [resp.message.id]: resp.usage! }));
      }
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInput(content);
      setError(e instanceof ApiError ? e.message : "전송 실패");
    } finally {
      setLoading(false);
    }
  };

  const stats = conversation.extraction_stats;

  return (
    <div style={s.container}>
      <div style={s.header}>
        <span style={s.title}>{conversation.title || "새 대화"}</span>
        <span style={s.pages}>{conversation.pages_display}</span>
      </div>

      {stats && (
        <div style={s.statsBanner}>
          <span>OCR</span>
          <span style={s.statsSep}>·</span>
          <span>{stats.backend}</span>
          <span style={s.statsSep}>·</span>
          <span>{stats.page_count}페이지</span>
          <span style={s.statsSep}>·</span>
          <span>{stats.elapsed_s}s</span>
          {stats.cost_usd != null && (
            <>
              <span style={s.statsSep}>·</span>
              <span>{fmtCost(stats.cost_usd)}</span>
            </>
          )}
        </div>
      )}

      <div style={s.msgList}>
        {messages.map((msg) => (
          <div key={msg.id} style={msg.role === "user" ? s.userRow : s.assistantRow}>
            <div style={msg.role === "user" ? s.userBubble : s.assistantBubble}>
              {msg.content}
            </div>
            {msg.role === "assistant" && usageMap[msg.id] && (
              <UsageBadge usage={usageMap[msg.id]} />
            )}
          </div>
        ))}
        {loading && (
          <div style={s.assistantRow}>
            <div style={s.assistantBubble}>…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p style={s.error}>{error}</p>}

      <div style={s.inputRow}>
        <textarea
          style={s.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          placeholder="메시지 입력 (Enter 전송, Shift+Enter 줄바꿈)"
          rows={2}
          disabled={loading}
        />
        <button
          style={loading || !input.trim() ? s.btnDisabled : s.btn}
          onClick={submit}
          disabled={loading || !input.trim()}
        >전송</button>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", height: "100%", gap: 8 },
  header: { display: "flex", alignItems: "baseline", gap: 8 },
  title: { fontSize: 15, fontWeight: 700, color: "#222" },
  pages: { fontSize: 12, color: "#888" },
  statsBanner: {
    display: "flex", alignItems: "center", gap: 6,
    fontSize: 11, color: "#888", background: "#f7f7f7",
    border: "1px solid #e8e8e8", borderRadius: 4, padding: "4px 10px",
    flexWrap: "wrap" as const,
  },
  statsSep: { color: "#ccc" },
  msgList: { flex: 1, overflowY: "auto" as const, display: "flex", flexDirection: "column", gap: 10, padding: "4px 0" },
  userRow: { display: "flex", flexDirection: "column" as const, alignItems: "flex-end" },
  assistantRow: { display: "flex", flexDirection: "column" as const, alignItems: "flex-start" },
  userBubble: { background: "#1a1a1a", color: "#fff", borderRadius: "12px 12px 2px 12px", padding: "8px 14px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap" as const },
  assistantBubble: { background: "#f0f0f0", color: "#222", borderRadius: "12px 12px 12px 2px", padding: "8px 14px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap" as const },
  usageBadge: {
    display: "flex", alignItems: "center", gap: 5,
    fontSize: 10, color: "#aaa", marginTop: 3, paddingLeft: 2,
  },
  usageModel: { fontFamily: "monospace", color: "#999" },
  usageSep: { color: "#ddd" },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
  inputRow: { display: "flex", gap: 8, alignItems: "flex-end" },
  textarea: { flex: 1, padding: "8px 12px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13, fontFamily: "inherit", resize: "none" as const },
  btn: { padding: "8px 16px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "pointer" },
  btnDisabled: { padding: "8px 16px", background: "#ccc", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "not-allowed" },
};
