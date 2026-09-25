import { useState } from "react";
import { createConversation, ApiError } from "../api";
import type { Book, Conversation, PdfFile } from "../types";

interface Props {
  book: Book;
  pdf: PdfFile;
  onCreated: (conv: Conversation) => void;
  onCancel: () => void;
}

export default function NewChatForm({ book, pdf, onCreated, onCancel }: Props) {
  const [pagesStr, setPagesStr] = useState("");
  const [useHighlights, setUseHighlights] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!pagesStr.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const conv = await createConversation(book.id, pdf.id, pagesStr.trim(), useHighlights);
      onCreated(conv);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "대화 시작 실패");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.container}>
      <p style={s.label}>
        <strong>{pdf.label}</strong>의 페이지 범위를 입력하세요
      </p>
      <input
        style={s.input}
        placeholder="예: 10-15, 21"
        value={pagesStr}
        autoFocus
        onChange={(e) => setPagesStr(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        disabled={loading}
      />
      <label style={s.checkLabel}>
        <input
          type="checkbox"
          checked={useHighlights}
          onChange={(e) => setUseHighlights(e.target.checked)}
          disabled={loading}
          style={s.checkbox}
        />
        형광 표시를 LLM 컨텍스트에 반영
      </label>
      {error && <p style={s.error}>{error}</p>}
      <div style={s.btns}>
        <button style={loading ? s.btnDisabled : s.btn} onClick={submit} disabled={loading}>
          {loading ? "추출 중…" : "대화 시작"}
        </button>
        <button style={s.btnGhost} onClick={onCancel} disabled={loading}>취소</button>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", gap: 10, maxWidth: 400 },
  label: { margin: 0, fontSize: 14, color: "#333" },
  input: { padding: "8px 12px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14 },
  checkLabel: { display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#555", cursor: "pointer", userSelect: "none" },
  checkbox: { margin: 0, cursor: "pointer" },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
  btns: { display: "flex", gap: 8 },
  btn: { padding: "7px 16px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "pointer" },
  btnDisabled: { padding: "7px 16px", background: "#999", color: "#fff", border: "none", borderRadius: 4, fontSize: 13, cursor: "not-allowed" },
  btnGhost: { padding: "7px 16px", background: "none", color: "#555", border: "1px solid #ccc", borderRadius: 4, fontSize: 13, cursor: "pointer" },
};
