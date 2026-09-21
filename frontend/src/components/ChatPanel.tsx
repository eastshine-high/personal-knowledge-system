import { useEffect, useRef, useState } from "react";
import { getMessages, sendMessage, ApiError } from "../api";
import type { Conversation, Message } from "../types";

interface Props {
  conversation: Conversation;
}

export default function ChatPanel({ conversation }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMessages(conversation.id).then(setMessages).catch(() => {});
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
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInput(content);
      setError(e instanceof ApiError ? e.message : "전송 실패");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.container}>
      <div style={s.header}>
        <span style={s.title}>{conversation.title || "새 대화"}</span>
        <span style={s.pages}>{conversation.pages_display}</span>
      </div>

      <div style={s.msgList}>
        {messages.map((msg) => (
          <div key={msg.id} style={msg.role === "user" ? s.userRow : s.assistantRow}>
            <div style={msg.role === "user" ? s.userBubble : s.assistantBubble}>
              {msg.content}
            </div>
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
  msgList: { flex: 1, overflowY: "auto" as const, display: "flex", flexDirection: "column", gap: 10, padding: "4px 0" },
  userRow: { display: "flex", justifyContent: "flex-end" },
  assistantRow: { display: "flex", justifyContent: "flex-start" },
  userBubble: { background: "#1a1a1a", color: "#fff", borderRadius: "12px 12px 2px 12px", padding: "8px 14px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap" as const },
  assistantBubble: { background: "#f0f0f0", color: "#222", borderRadius: "12px 12px 12px 2px", padding: "8px 14px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap" as const },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
  inputRow: { display: "flex", gap: 8, alignItems: "flex-end" },
  textarea: { flex: 1, padding: "8px 12px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13, fontFamily: "inherit", resize: "none" as const },
  btn: { padding: "8px 16px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "pointer" },
  btnDisabled: { padding: "8px 16px", background: "#ccc", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "not-allowed" },
};
