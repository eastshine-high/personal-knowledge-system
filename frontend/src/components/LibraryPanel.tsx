import { useEffect, useState } from "react";
import { addPdf, createBook, deletePdf, getBooks, ApiError } from "../api";
import type { Book, PdfFile } from "../types";

interface Props {
  selectedPdfId: string | null;
  onSelectPdf: (pdf: PdfFile, book: Book) => void;
}

export default function LibraryPanel({ selectedPdfId, onSelectPdf }: Props) {
  const [books, setBooks] = useState<Book[]>([]);
  const [expandedBookId, setExpandedBookId] = useState<string | null>(null);
  const [addingBook, setAddingBook] = useState(false);
  const [newBookTitle, setNewBookTitle] = useState("");
  const [addingPdfTo, setAddingPdfTo] = useState<string | null>(null);
  const [newPdfLabel, setNewPdfLabel] = useState("");
  const [newPdfPath, setNewPdfPath] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBooks().then(setBooks).catch(() => {});
  }, []);

  const submitBook = async () => {
    if (!newBookTitle.trim()) return;
    try {
      const book = await createBook(newBookTitle.trim());
      setBooks((prev) => [book, ...prev]);
      setNewBookTitle("");
      setAddingBook(false);
      setExpandedBookId(book.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "책 추가 실패");
    }
  };

  const submitPdf = async (bookId: string) => {
    if (!newPdfLabel.trim() || !newPdfPath.trim()) return;
    try {
      const pf = await addPdf(bookId, newPdfLabel.trim(), newPdfPath.trim());
      setBooks((prev) =>
        prev.map((b) => b.id === bookId ? { ...b, pdf_files: [...b.pdf_files, pf] } : b)
      );
      setNewPdfLabel("");
      setNewPdfPath("");
      setAddingPdfTo(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "PDF 추가 실패");
    }
  };

  const removePdf = async (bookId: string, pdfId: string) => {
    try {
      await deletePdf(bookId, pdfId);
      setBooks((prev) =>
        prev.map((b) =>
          b.id === bookId ? { ...b, pdf_files: b.pdf_files.filter((p) => p.id !== pdfId) } : b
        )
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "PDF 삭제 실패");
    }
  };

  return (
    <div style={s.panel}>
      <div style={s.headingRow}>
        <p style={s.heading}>서재</p>
        {!addingBook && (
          <button style={s.addBookBtn} onClick={() => setAddingBook(true)}>+ 책 추가</button>
        )}
      </div>
      {addingBook && (
        <div style={s.inlineForm}>
          <input
            style={s.input}
            placeholder="책 제목"
            value={newBookTitle}
            autoFocus
            onChange={(e) => setNewBookTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitBook()}
          />
          <div style={s.formBtns}>
            <button style={s.btnSm} onClick={submitBook}>추가</button>
            <button style={s.btnSmGhost} onClick={() => setAddingBook(false)}>취소</button>
          </div>
        </div>
      )}
      {error && <p style={s.error} onClick={() => setError(null)}>{error}</p>}

      <div style={s.bookList}>
        {books.map((book) => (
          <div key={book.id}>
            <button
              style={s.bookBtn}
              onClick={() => setExpandedBookId(expandedBookId === book.id ? null : book.id)}
            >
              <span style={s.bookIcon}>📚</span>
              <span style={s.bookTitle}>{book.title}</span>
              <span style={s.chevron}>{expandedBookId === book.id ? "▾" : "▸"}</span>
            </button>

            {expandedBookId === book.id && (
              <div style={s.pdfList}>
                {book.pdf_files.map((pf) => (
                  <div
                    key={pf.id}
                    style={pf.id === selectedPdfId ? s.pdfItemSelected : s.pdfItem}
                    onClick={() => onSelectPdf(pf, book)}
                  >
                    <span style={s.pdfLabel}>{pf.label}</span>
                    <button
                      style={s.deleteBtn}
                      onClick={(e) => { e.stopPropagation(); removePdf(book.id, pf.id); }}
                    >✕</button>
                  </div>
                ))}

                {addingPdfTo === book.id ? (
                  <div style={s.inlineForm}>
                    <input
                      style={s.input}
                      placeholder="레이블 (예: 1부)"
                      value={newPdfLabel}
                      onChange={(e) => setNewPdfLabel(e.target.value)}
                    />
                    <input
                      style={s.input}
                      placeholder="PDF 경로"
                      value={newPdfPath}
                      onChange={(e) => setNewPdfPath(e.target.value)}
                    />
                    <div style={s.formBtns}>
                      <button style={s.btnSm} onClick={() => submitPdf(book.id)}>추가</button>
                      <button style={s.btnSmGhost} onClick={() => setAddingPdfTo(null)}>취소</button>
                    </div>
                  </div>
                ) : (
                  <button style={s.addPdfBtn} onClick={() => setAddingPdfTo(book.id)}>
                    + PDF 추가
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  panel: { display: "flex", flexDirection: "column", height: "100%", padding: "12px 8px", gap: 4 },
  headingRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 },
  heading: { margin: 0, fontSize: 13, fontWeight: 700, color: "#333" },
  error: { margin: 0, fontSize: 11, color: "#d32f2f", cursor: "pointer", padding: "4px 0" },
  bookList: { flex: 1, overflowY: "auto" as const },
  bookBtn: {
    display: "flex", alignItems: "center", gap: 4, width: "100%",
    background: "none", border: "none", cursor: "pointer",
    padding: "5px 4px", borderRadius: 4, textAlign: "left" as const,
    fontSize: 13,
  },
  bookIcon: { fontSize: 14 },
  bookTitle: { flex: 1, fontWeight: 600, color: "#222", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  chevron: { fontSize: 11, color: "#888" },
  pdfList: { paddingLeft: 20, display: "flex", flexDirection: "column", gap: 2, marginBottom: 4 },
  pdfItem: {
    display: "flex", alignItems: "center", gap: 4,
    padding: "4px 6px", borderRadius: 4, cursor: "pointer", fontSize: 12, color: "#444",
  },
  pdfItemSelected: {
    display: "flex", alignItems: "center", gap: 4,
    padding: "4px 6px", borderRadius: 4, cursor: "pointer", fontSize: 12,
    background: "#e3f2fd", color: "#1565c0", fontWeight: 600,
  },
  pdfLabel: { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  deleteBtn: { background: "none", border: "none", cursor: "pointer", color: "#bbb", fontSize: 11, padding: 0 },
  addPdfBtn: {
    background: "none", border: "1px dashed #ccc", borderRadius: 4,
    color: "#888", fontSize: 11, cursor: "pointer", padding: "3px 8px", marginTop: 2,
  },
  addBookBtn: {
    background: "none", border: "1px dashed #ccc", borderRadius: 4,
    color: "#666", fontSize: 11, cursor: "pointer", padding: "3px 8px",
  },
  inlineForm: { display: "flex", flexDirection: "column", gap: 4, padding: "4px 0" },
  input: { padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, fontSize: 12 },
  formBtns: { display: "flex", gap: 4 },
  btnSm: { padding: "3px 10px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 4, fontSize: 11, cursor: "pointer" },
  btnSmGhost: { padding: "3px 10px", background: "none", color: "#666", border: "1px solid #ccc", borderRadius: 4, fontSize: 11, cursor: "pointer" },
};
