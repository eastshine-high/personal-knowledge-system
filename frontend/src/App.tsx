import { useState } from "react";
import type { NoteResponse, SessionResponse } from "./types";
import InputForm from "./components/InputForm";
import PdfViewer from "./components/PdfViewer";
import NotePanel from "./components/NotePanel";
import RefineChat from "./components/RefineChat";
import Toolbar from "./components/Toolbar";

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(null);

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

  return (
    <main style={styles.workspace}>
      <section style={styles.left}>
        <h2 style={styles.panelTitle}>소스 패널</h2>
        <PdfViewer sessionId={session.session_id} pages={session.notes[0]?.pages ?? []} />
      </section>
      <section style={styles.right}>
        <div style={styles.panelHeader}>
          <h2 style={styles.panelTitle}>작업 패널</h2>
          <Toolbar sessionId={session.session_id} onSessionUpdated={setSession} />
        </div>
        {session.notes[0] && (
          <NotePanel
            sessionId={session.session_id}
            note={session.notes[0]}
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
};
