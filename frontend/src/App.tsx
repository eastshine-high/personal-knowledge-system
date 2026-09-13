import { useEffect, useState } from "react";
import type { NoteResponse, SessionResponse } from "./types";
import InputForm from "./components/InputForm";
import PdfViewer from "./components/PdfViewer";
import NotePanel from "./components/NotePanel";
import RefineChat from "./components/RefineChat";
import Toolbar from "./components/Toolbar";

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);

  // 새 세션이 생성될 때 첫 번째 노트 선택
  useEffect(() => {
    if (session) setSelectedNoteId(session.notes[0]?.id ?? null);
  }, [session?.session_id]);

  const handleNoteUpdated = (updated: NoteResponse) => {
    setSession((prev) =>
      prev
        ? { ...prev, notes: prev.notes.map((n) => (n.id === updated.id ? updated : n)) }
        : prev,
    );
  };

  if (!session) {
    return (
      <main style={styles.center}>
        <InputForm onSessionCreated={setSession} />
      </main>
    );
  }

  const currentNote =
    session.notes.find((n) => n.id === selectedNoteId) ?? session.notes[0] ?? null;
  const multiNote = session.notes.length > 1;

  return (
    <main style={styles.workspace}>
      <section style={styles.left}>
        <h2 style={styles.panelTitle}>소스 패널</h2>
        <PdfViewer sessionId={session.session_id} pages={currentNote?.pages ?? []} />
      </section>
      <section style={styles.right}>
        <div style={styles.panelHeader}>
          <h2 style={styles.panelTitle}>작업 패널</h2>
          <Toolbar sessionId={session.session_id} onSessionUpdated={setSession} />
        </div>

        {multiNote && (
          <div style={styles.tabBar} role="tablist">
            {session.notes.map((note, idx) => (
              <button
                key={note.id}
                role="tab"
                aria-selected={note.id === currentNote?.id}
                style={note.id === currentNote?.id ? styles.tabActive : styles.tab}
                onClick={() => setSelectedNoteId(note.id)}
              >
                {note.title || `노트 ${idx + 1}`}
              </button>
            ))}
          </div>
        )}

        {currentNote && (
          <NotePanel
            sessionId={session.session_id}
            note={currentNote}
            onNoteUpdated={handleNoteUpdated}
          />
        )}
        <RefineChat
          sessionId={session.session_id}
          events={session.events}
          onSessionUpdated={setSession}
        />
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  center: {
    display: "flex",
    height: "100vh",
    alignItems: "center",
    justifyContent: "center",
    background: "#f5f5f5",
    fontFamily: "sans-serif",
  },
  workspace: {
    display: "flex",
    height: "100vh",
    fontFamily: "sans-serif",
  },
  left: {
    flex: 1,
    borderRight: "1px solid #e0e0e0",
    padding: 16,
    overflowY: "auto",
  },
  right: {
    flex: 1,
    padding: 16,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  panelHeader: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  panelTitle: { margin: 0, fontSize: 16, fontWeight: 600 },
  tabBar: {
    display: "flex",
    gap: 4,
    borderBottom: "1px solid #e0e0e0",
    paddingBottom: 0,
  },
  tab: {
    padding: "6px 14px",
    background: "none",
    border: "1px solid #e0e0e0",
    borderBottom: "none",
    borderRadius: "4px 4px 0 0",
    fontSize: 13,
    cursor: "pointer",
    color: "#666",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: 160,
  },
  tabActive: {
    padding: "6px 14px",
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderBottom: "1px solid #fff",
    borderRadius: "4px 4px 0 0",
    fontSize: 13,
    cursor: "pointer",
    color: "#1a1a1a",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: 160,
    marginBottom: -1,
  },
};
