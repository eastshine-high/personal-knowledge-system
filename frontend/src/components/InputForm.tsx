import { useState } from "react";
import { createSession, ApiError } from "../api";
import type { SessionResponse } from "../types";

interface Props {
  onSessionCreated: (session: SessionResponse) => void;
}

export default function InputForm({ onSessionCreated }: Props) {
  const [pdfPath, setPdfPath] = useState("");
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [topic, setTopic] = useState("");
  const [guideline, setGuideline] = useState("");
  const [noteCount, setNoteCount] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const session = await createSession({
        pdf_path: pdfPath,
        page_start: pageStart,
        page_end: pageEnd,
        topic,
        guideline: guideline || undefined,
        note_count: noteCount,
      });
      onSessionCreated(session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <h2 style={styles.title}>PDF 개념 요약 노트</h2>

      <label style={styles.label}>
        PDF 경로
        <input
          style={styles.input}
          type="text"
          value={pdfPath}
          onChange={(e) => setPdfPath(e.target.value)}
          placeholder="/path/to/document.pdf"
          required
        />
      </label>

      <div style={styles.row}>
        <label style={{ ...styles.label, flex: 1 }}>
          시작 페이지
          <input
            style={styles.input}
            type="number"
            min={1}
            value={pageStart}
            onChange={(e) => setPageStart(Number(e.target.value))}
            required
          />
        </label>
        <label style={{ ...styles.label, flex: 1 }}>
          끝 페이지
          <input
            style={styles.input}
            type="number"
            min={1}
            value={pageEnd}
            onChange={(e) => setPageEnd(Number(e.target.value))}
            required
          />
        </label>
        <label style={{ ...styles.label, flex: 1 }}>
          노트 수
          <input
            style={styles.input}
            type="number"
            min={1}
            max={5}
            value={noteCount}
            onChange={(e) => setNoteCount(Number(e.target.value))}
          />
        </label>
      </div>

      <label style={styles.label}>
        주제
        <input
          style={styles.input}
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="예: 셀프 어텐션 메커니즘"
          required
        />
      </label>

      <label style={styles.label}>
        가이드라인 (선택)
        <textarea
          style={{ ...styles.input, height: 72, resize: "vertical" }}
          value={guideline}
          onChange={(e) => setGuideline(e.target.value)}
          placeholder="예: 핵심 개념 위주로, 수식 포함"
        />
      </label>

      {error && <p style={styles.error}>{error}</p>}

      <button style={loading ? styles.buttonDisabled : styles.button} type="submit" disabled={loading}>
        {loading ? "노트 생성 중…" : "노트 생성"}
      </button>
    </form>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    width: 480,
    padding: 32,
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    background: "#fff",
  },
  title: { margin: 0, fontSize: 20, fontWeight: 600 },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    fontSize: 14,
    color: "#333",
  },
  input: {
    padding: "8px 10px",
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 14,
    outline: "none",
  },
  row: { display: "flex", gap: 12 },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
  button: {
    padding: "10px 0",
    background: "#1a1a1a",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 14,
    cursor: "pointer",
  },
  buttonDisabled: {
    padding: "10px 0",
    background: "#999",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 14,
    cursor: "not-allowed",
  },
};
