import { useEffect, useState } from "react";
import { undoSession, exportUrl, ApiError } from "../api";
import type { SessionResponse } from "../types";

interface Props {
  sessionId: string;
  onSessionUpdated: (session: SessionResponse) => void;
}

export default function Toolbar({ sessionId, onSessionUpdated }: Props) {
  const [undoing, setUndoing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 에러 메시지 3초 후 자동 소멸
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 3000);
    return () => clearTimeout(t);
  }, [error]);

  const handleUndo = async () => {
    setUndoing(true);
    try {
      const session = await undoSession(sessionId);
      onSessionUpdated(session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "undo 실패");
    } finally {
      setUndoing(false);
    }
  };

  return (
    <div style={styles.container}>
      {error && <span style={styles.error}>{error}</span>}
      <button style={undoing ? styles.btnDisabled : styles.btn} onClick={handleUndo} disabled={undoing}>
        {undoing ? "…" : "↩ undo"}
      </button>
      <a href={exportUrl(sessionId)} download style={styles.exportBtn}>
        ↓ 내보내기
      </a>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: "flex", alignItems: "center", gap: 8 },
  btn: {
    padding: "5px 12px",
    background: "#fff",
    color: "#333",
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 13,
    cursor: "pointer",
  },
  btnDisabled: {
    padding: "5px 12px",
    background: "#f5f5f5",
    color: "#aaa",
    border: "1px solid #e0e0e0",
    borderRadius: 4,
    fontSize: 13,
    cursor: "not-allowed",
  },
  exportBtn: {
    padding: "5px 12px",
    background: "#1a1a1a",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    textDecoration: "none",
    cursor: "pointer",
  },
  error: {
    fontSize: 12,
    color: "#d32f2f",
    background: "#fff3f3",
    border: "1px solid #ffcdd2",
    borderRadius: 4,
    padding: "3px 8px",
  },
};
