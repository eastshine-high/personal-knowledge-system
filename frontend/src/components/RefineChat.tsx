import { useEffect, useRef, useState } from "react";
import { refineSession, ApiError } from "../api";
import type { EventResponse, SessionResponse } from "../types";

interface Props {
  sessionId: string;
  events: EventResponse[];
  onSessionUpdated: (session: SessionResponse) => void;
}

const EVENT_LABELS: Record<string, string> = {
  start: "노트 생성됨",
  apply_edit: "직접 편집",
  revert: "되돌림",
};

export default function RefineChat({ sessionId, events, onSessionUpdated }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  const submit = async () => {
    const inst = instruction.trim();
    if (!inst || loading) return;
    setError(null);
    setLoading(true);
    setInstruction("");
    try {
      const session = await refineSession(sessionId, inst);
      onSessionUpdated(session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "리파인 실패");
      setInstruction(inst);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div style={styles.container}>
      <p style={styles.heading}>리파인</p>

      <div style={styles.history}>
        {events.map((ev) =>
          ev.action === "refine" ? (
            <div key={ev.seq} style={styles.refineBubble}>
              <span style={styles.bubbleText}>{ev.content}</span>
            </div>
          ) : (
            <div key={ev.seq} style={styles.systemMsg}>
              {EVENT_LABELS[ev.action] ?? ev.action}
            </div>
          ),
        )}
        {loading && <div style={styles.systemMsg}>리파인 중…</div>}
        <div ref={bottomRef} />
      </div>

      {error && <p style={styles.error}>{error}</p>}

      <div style={styles.inputRow}>
        <textarea
          style={styles.textarea}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="지시 입력 (Shift+Enter 줄바꿈, Enter 전송)"
          disabled={loading}
          rows={2}
        />
        <button
          style={loading || !instruction.trim() ? styles.btnDisabled : styles.btn}
          onClick={submit}
          disabled={loading || !instruction.trim()}
        >
          전송
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    borderTop: "1px solid #e0e0e0",
    paddingTop: 12,
  },
  heading: { margin: 0, fontSize: 13, fontWeight: 600, color: "#555" },
  history: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    maxHeight: 180,
    overflowY: "auto",
    padding: "4px 0",
  },
  refineBubble: {
    alignSelf: "flex-end",
    background: "#1a1a1a",
    color: "#fff",
    borderRadius: "12px 12px 2px 12px",
    padding: "6px 12px",
    maxWidth: "85%",
  },
  bubbleText: { fontSize: 13, lineHeight: 1.5 },
  systemMsg: {
    alignSelf: "center",
    fontSize: 11,
    color: "#999",
    background: "#f0f0f0",
    borderRadius: 10,
    padding: "2px 10px",
  },
  inputRow: { display: "flex", gap: 8, alignItems: "flex-end" },
  textarea: {
    flex: 1,
    padding: "8px 10px",
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 13,
    fontFamily: "inherit",
    resize: "none",
    lineHeight: 1.5,
  },
  btn: {
    padding: "8px 16px",
    background: "#1a1a1a",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  btnDisabled: {
    padding: "8px 16px",
    background: "#ccc",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    cursor: "not-allowed",
    whiteSpace: "nowrap",
  },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
};
