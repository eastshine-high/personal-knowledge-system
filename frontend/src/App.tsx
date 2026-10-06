import { useState, useEffect } from "react";
import type { Book, Conversation, NoteResponse, PdfFile, SessionResponse } from "./types";
import InputForm from "./components/InputForm";
import PdfViewer from "./components/PdfViewer";
import NotePanel from "./components/NotePanel";
import RefineChat from "./components/RefineChat";
import Toolbar from "./components/Toolbar";
import LibraryPanel from "./components/LibraryPanel";
import ConversationList from "./components/ConversationList";
import NewChatForm from "./components/NewChatForm";
import ChatPanel from "./components/ChatPanel";

type MainView =
  | { kind: "empty" }
  | { kind: "conversation-list" }
  | { kind: "new-chat" }
  | { kind: "chat"; conv: Conversation }
  | { kind: "note-session"; session: SessionResponse };

export default function App() {
  const [selectedPdf, setSelectedPdf] = useState<{ pdf: PdfFile; book: Book } | null>(null);
  const [mainView, setMainView] = useState<MainView>({ kind: "empty" });
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [newConv, setNewConv] = useState<Conversation | null>(null);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(220);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);

  useEffect(() => {
    if (!showNoteModal) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowNoteModal(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [showNoteModal]);

  useEffect(() => {
    if (!isResizingSidebar) return;
    const handleMove = (e: MouseEvent) => {
      setSidebarWidth(Math.min(480, Math.max(160, e.clientX)));
    };
    const handleUp = () => setIsResizingSidebar(false);
    document.addEventListener("mousemove", handleMove);
    document.addEventListener("mouseup", handleUp);
    return () => {
      document.removeEventListener("mousemove", handleMove);
      document.removeEventListener("mouseup", handleUp);
    };
  }, [isResizingSidebar]);

  const handleSelectPdf = (pdf: PdfFile, book: Book) => {
    setSelectedPdf({ pdf, book });
    setMainView({ kind: "conversation-list" });
    setNewConv(null);
  };

  const handleConvCreated = (conv: Conversation) => {
    setNewConv(conv);
    setMainView({ kind: "chat", conv });
  };

  const handleSelectConv = (conv: Conversation) => {
    setMainView({ kind: "chat", conv });
  };

  const handleNoteSessionCreated = (session: SessionResponse) => {
    setSelectedNoteId(session.notes[0]?.id ?? null);
    setMainView({ kind: "note-session", session });
    setShowNoteModal(false);
  };

  const handleNoteUpdated = (updated: NoteResponse) => {
    if (mainView.kind !== "note-session") return;
    const session = mainView.session;
    setMainView({
      kind: "note-session",
      session: { ...session, notes: session.notes.map((n) => n.id === updated.id ? updated : n) },
    });
  };

  const handleSessionUpdated = (session: SessionResponse) => {
    if (mainView.kind !== "note-session") return;
    setMainView({ kind: "note-session", session });
  };

  return (
    <main style={s.workspace}>
      {/* 좌측 서재 패널 */}
      <aside style={{ ...s.sidebar, width: sidebarWidth }}>
        <LibraryPanel selectedPdfId={selectedPdf?.pdf.id ?? null} onSelectPdf={handleSelectPdf} />
      </aside>
      <div
        style={s.resizeHandle}
        onMouseDown={() => setIsResizingSidebar(true)}
      />

      {/* 우측 메인 영역 */}
      <section style={s.main}>
        {/* 상단 바 */}
        <div style={s.topBar}>
          <div style={s.topBarLeft}>
            <span style={s.appTitle}>PKS</span>
            {selectedPdf && (
              <div style={s.pdfBreadcrumb}>
                <span style={s.pdfBreadcrumbBook}>{selectedPdf.book.title}</span>
                <span style={s.pdfBreadcrumbSep}>·</span>
                <span style={s.pdfBreadcrumbLabel}>{selectedPdf.pdf.label}</span>
                <span style={s.pdfBreadcrumbSep}>·</span>
                <span style={s.pdfBreadcrumbPath}>{selectedPdf.pdf.pdf_path}</span>
              </div>
            )}
          </div>
          <button data-testid="open-note-modal-btn" style={s.noteBtn} onClick={() => setShowNoteModal(true)}>
            노트 생성
          </button>
        </div>

        {/* 노트 생성 모달 */}
        {showNoteModal && (
          <div style={s.modalOverlay} onClick={(e) => { if (e.target === e.currentTarget) setShowNoteModal(false); }}>
            <div style={s.modal}>
              <InputForm onSessionCreated={handleNoteSessionCreated} />
            </div>
          </div>
        )}

        {/* 메인 콘텐츠 */}
        <div style={s.content}>
          {mainView.kind === "empty" && (
            <div style={s.emptyState}>
              <p style={s.emptyText}>서재에서 PDF를 선택하거나</p>
              <p style={s.emptyText}>노트 생성 버튼을 눌러 시작하세요</p>
            </div>
          )}

          {mainView.kind === "conversation-list" && selectedPdf && (
            <ConversationList
              book={selectedPdf.book}
              pdf={selectedPdf.pdf}
              selectedConvId={mainView.kind === "conversation-list" ? null : null}
              onSelectConv={handleSelectConv}
              onNewChat={() => setMainView({ kind: "new-chat" })}
              newConv={newConv}
            />
          )}

          {mainView.kind === "new-chat" && selectedPdf && (
            <NewChatForm
              book={selectedPdf.book}
              pdf={selectedPdf.pdf}
              onCreated={handleConvCreated}
              onCancel={() => setMainView({ kind: "conversation-list" })}
            />
          )}

          {mainView.kind === "chat" && (
            <ChatPanel conversation={mainView.conv} />
          )}

          {mainView.kind === "note-session" && (() => {
            const { session } = mainView;
            const currentNote =
              session.notes.find((n) => n.id === selectedNoteId) ?? session.notes[0] ?? null;
            const multiNote = session.notes.length > 1;
            return (
              <div style={s.noteWorkspace}>
                <section style={s.sourcePanel}>
                  <h2 style={s.panelTitle}>소스 패널</h2>
                  <PdfViewer sessionId={session.session_id} pages={currentNote?.pages ?? []} />
                </section>
                <section style={s.workPanel}>
                  <div style={s.panelHeader}>
                    <h2 style={s.panelTitle}>작업 패널</h2>
                    <Toolbar sessionId={session.session_id} onSessionUpdated={handleSessionUpdated} />
                  </div>
                  {multiNote && (
                    <div style={s.tabBar} role="tablist">
                      {session.notes.map((note, idx) => (
                        <button
                          key={note.id}
                          role="tab"
                          aria-selected={note.id === currentNote?.id}
                          style={note.id === currentNote?.id ? s.tabActive : s.tab}
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
                    onSessionUpdated={handleSessionUpdated}
                  />
                </section>
              </div>
            );
          })()}
        </div>
      </section>
    </main>
  );
}

const s: Record<string, React.CSSProperties> = {
  workspace: { display: "flex", height: "100vh", fontFamily: "sans-serif", background: "#fafafa" },
  sidebar: { background: "#fff", flexShrink: 0, overflow: "hidden" },
  resizeHandle: { width: 5, marginLeft: -2, flexShrink: 0, cursor: "col-resize", background: "transparent", borderRight: "1px solid #e0e0e0" },
  main: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" },
  topBar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "10px 16px", borderBottom: "1px solid #e0e0e0", background: "#fff",
    minWidth: 0,
  },
  topBarLeft: { display: "flex", alignItems: "baseline", gap: 12, minWidth: 0, overflow: "hidden" },
  appTitle: { fontSize: 15, fontWeight: 700, color: "#1a1a1a", flexShrink: 0 },
  pdfBreadcrumb: { display: "flex", alignItems: "baseline", gap: 5, minWidth: 0, overflow: "hidden" },
  pdfBreadcrumbBook: { fontSize: 12, fontWeight: 600, color: "#555", flexShrink: 0 },
  pdfBreadcrumbSep: { fontSize: 11, color: "#ccc", flexShrink: 0 },
  pdfBreadcrumbLabel: { fontSize: 12, color: "#777", flexShrink: 0 },
  pdfBreadcrumbPath: { fontSize: 11, color: "#aaa", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  noteBtn: {
    padding: "6px 14px", background: "#1a1a1a", color: "#fff",
    border: "none", borderRadius: 4, fontSize: 13, cursor: "pointer",
  },
  content: { flex: 1, overflowY: "auto", padding: 20 },
  emptyState: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "60vh", gap: 4 },
  emptyText: { margin: 0, fontSize: 14, color: "#aaa" },
  // 모달
  modalOverlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
  },
  modal: {
    background: "#fff", borderRadius: 8, padding: 24, boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
    maxWidth: 520, width: "90%", maxHeight: "90vh", overflowY: "auto",
  },
  // 노트 세션 2분할
  noteWorkspace: { display: "flex", height: "100%", gap: 0 },
  sourcePanel: { flex: 1, borderRight: "1px solid #e0e0e0", padding: 16, overflowY: "auto" },
  workPanel: { flex: 1, padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 },
  panelHeader: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  panelTitle: { margin: 0, fontSize: 16, fontWeight: 600 },
  tabBar: { display: "flex", gap: 4, borderBottom: "1px solid #e0e0e0" },
  tab: {
    padding: "6px 14px", background: "none", border: "1px solid #e0e0e0",
    borderBottom: "none", borderRadius: "4px 4px 0 0", fontSize: 13, cursor: "pointer",
    color: "#666", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160,
  },
  tabActive: {
    padding: "6px 14px", background: "#fff", border: "1px solid #e0e0e0",
    borderBottom: "1px solid #fff", borderRadius: "4px 4px 0 0", fontSize: 13, cursor: "pointer",
    color: "#1a1a1a", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden",
    textOverflow: "ellipsis", maxWidth: 160, marginBottom: -1,
  },
};
