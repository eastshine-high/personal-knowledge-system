import { useEffect, useState } from "react";
import { getConversations } from "../api";
import type { Book, Conversation, PdfFile } from "../types";

interface Props {
  book: Book;
  pdf: PdfFile;
  selectedConvId: string | null;
  onSelectConv: (conv: Conversation) => void;
  onNewChat: () => void;
  newConv?: Conversation | null;
}

export default function ConversationList({ book, pdf, selectedConvId, onSelectConv, onNewChat, newConv }: Props) {
  const [convs, setConvs] = useState<Conversation[]>([]);

  useEffect(() => {
    getConversations(book.id).catch(() => []).then(setConvs);
  }, [book.id]);

  useEffect(() => {
    if (newConv) {
      setConvs((prev) => [newConv, ...prev.filter((c) => c.id !== newConv.id)]);
    }
  }, [newConv]);

  return (
    <div style={s.container}>
      <div style={s.header}>
        <div>
          <span style={s.bookLabel}>{book.title}</span>
          <span style={s.pdfLabel}> · {pdf.label}</span>
        </div>
        <button style={s.newBtn} onClick={onNewChat}>+ 새 대화</button>
      </div>

      {convs.length === 0 ? (
        <p style={s.empty}>대화가 없습니다. 새 대화를 시작하세요.</p>
      ) : (
        <div style={s.list}>
          {convs.map((conv) => (
            <button
              key={conv.id}
              style={conv.id === selectedConvId ? s.itemSelected : s.item}
              onClick={() => onSelectConv(conv)}
            >
              <span style={s.title}>{conv.title || "새 대화"}</span>
              <span style={s.pages}>{conv.pages_display}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", gap: 8 },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  bookLabel: { fontSize: 14, fontWeight: 700, color: "#222" },
  pdfLabel: { fontSize: 13, color: "#666" },
  newBtn: {
    padding: "5px 12px", background: "#1a1a1a", color: "#fff",
    border: "none", borderRadius: 4, fontSize: 12, cursor: "pointer",
  },
  empty: { fontSize: 13, color: "#999", margin: 0 },
  list: { display: "flex", flexDirection: "column", gap: 4 },
  item: {
    display: "flex", flexDirection: "column", alignItems: "flex-start",
    gap: 2, padding: "8px 10px", background: "#f9f9f9",
    border: "1px solid #e8e8e8", borderRadius: 6, cursor: "pointer",
    textAlign: "left" as const, width: "100%",
  },
  itemSelected: {
    display: "flex", flexDirection: "column", alignItems: "flex-start",
    gap: 2, padding: "8px 10px", background: "#e3f2fd",
    border: "1px solid #90caf9", borderRadius: 6, cursor: "pointer",
    textAlign: "left" as const, width: "100%",
  },
  title: { fontSize: 13, fontWeight: 600, color: "#222" },
  pages: { fontSize: 11, color: "#888" },
};
