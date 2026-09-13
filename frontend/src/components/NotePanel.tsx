import { useEffect, useState } from "react";
import { editNote, ApiError } from "../api";
import type { NoteResponse } from "../types";

interface Props {
  sessionId: string;
  note: NoteResponse;
  onNoteUpdated: (note: NoteResponse) => void;
}

export default function NotePanel({ sessionId, note, onNoteUpdated }: Props) {
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(note.title);
  const [editBody, setEditBody] = useState(note.body);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // refine / undo 로 note가 교체되면 편집 상태 초기화
  useEffect(() => {
    setEditing(false);
    setEditTitle(note.title);
    setEditBody(note.body);
  }, [note.id, note.title, note.body]);

  const startEdit = () => {
    setEditTitle(note.title);
    setEditBody(note.body);
    setError(null);
    setEditing(true);
  };

  const cancelEdit = () => setEditing(false);

  const saveEdit = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await editNote(sessionId, note.id, editBody, editTitle || undefined);
      onNoteUpdated(updated);
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div style={styles.container}>
        <div style={styles.editHeader}>
          <span style={styles.sectionLabel}>편집 중</span>
          <div style={styles.editActions}>
            <button style={styles.btnSecondary} onClick={cancelEdit} disabled={saving}>취소</button>
            <button style={styles.btnPrimary} onClick={saveEdit} disabled={saving}>
              {saving ? "저장 중…" : "저장"}
            </button>
          </div>
        </div>
        <input
          style={styles.titleInput}
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          placeholder="제목"
        />
        <textarea
          style={styles.bodyTextarea}
          value={editBody}
          onChange={(e) => setEditBody(e.target.value)}
        />
        {error && <p style={styles.error}>{error}</p>}
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.viewHeader}>
        <h3 style={styles.noteTitle}>{note.title}</h3>
        <button style={styles.btnSecondary} onClick={startEdit}>편집</button>
      </div>

      <div style={styles.meta}>
        p.{note.pages.join(", ")} · {note.topic} · {note.created}
      </div>

      <pre style={styles.body}>{note.body}</pre>

      {note.figures.length > 0 && (
        <div style={styles.figures}>
          <p style={styles.figuresLabel}>그림</p>
          {note.figures.map((fig) => (
            <div key={fig.embed_name} style={styles.figureItem}>
              <code style={styles.embedName}>![[{fig.embed_name}]]</code>
              {fig.caption && <span style={styles.caption}>{fig.caption}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", gap: 12, height: "100%" },
  viewHeader: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 },
  editHeader: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  editActions: { display: "flex", gap: 8 },
  sectionLabel: { fontSize: 13, color: "#666" },
  noteTitle: { margin: 0, fontSize: 16, fontWeight: 600, flex: 1 },
  meta: { fontSize: 12, color: "#888" },
  body: {
    flex: 1,
    margin: 0,
    padding: 12,
    background: "#f9f9f9",
    border: "1px solid #e8e8e8",
    borderRadius: 4,
    fontSize: 13,
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    overflowY: "auto",
    fontFamily: "inherit",
  },
  titleInput: {
    padding: "6px 10px",
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 15,
    fontWeight: 600,
  },
  bodyTextarea: {
    flex: 1,
    padding: 12,
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 13,
    lineHeight: 1.7,
    fontFamily: "inherit",
    resize: "none",
    minHeight: 320,
  },
  figures: { borderTop: "1px solid #eee", paddingTop: 8 },
  figuresLabel: { margin: "0 0 6px", fontSize: 12, color: "#888", fontWeight: 600 },
  figureItem: { display: "flex", alignItems: "center", gap: 8, marginBottom: 4 },
  embedName: { fontSize: 12, background: "#eee", padding: "2px 6px", borderRadius: 3 },
  caption: { fontSize: 12, color: "#666" },
  btnPrimary: {
    padding: "6px 14px",
    background: "#1a1a1a",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    cursor: "pointer",
  },
  btnSecondary: {
    padding: "6px 14px",
    background: "#fff",
    color: "#333",
    border: "1px solid #ccc",
    borderRadius: 4,
    fontSize: 13,
    cursor: "pointer",
  },
  error: { margin: 0, fontSize: 13, color: "#d32f2f" },
};
