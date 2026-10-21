import { useEffect, useState } from "react";
import { createExtraction, deleteExtraction, getExtractions, ApiError } from "../api";
import type { Book, Extraction, PdfFile } from "../types";

interface Props {
  book: Book;
  pdf: PdfFile;
}

export default function ExtractionList({ book, pdf }: Props) {
  const [sets, setSets] = useState<Extraction[]>([]);
  const [topic, setTopic] = useState("");
  const [pagesStr, setPagesStr] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExtractions(book.id, pdf.id).catch(() => [] as Extraction[]).then(setSets);
  }, [book.id, pdf.id]);

  const submit = async () => {
    if (!topic.trim() || !pagesStr.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const ext = await createExtraction(book.id, pdf.id, topic.trim(), pagesStr.trim());
      setSets((prev) => [ext, ...prev]);
      setTopic("");
      setPagesStr("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "추출 세트 생성 실패");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    await deleteExtraction(book.id, pdf.id, id).catch(() => {});
    setSets((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div style={s.container}>
      <div style={s.sectionTitle}>추출 세트 (주제별 OCR)</div>

      <div style={s.form}>
        <input
          style={s.input}
          placeholder="주제 (예: 자료구조)"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={loading}
        />
        <input
          style={s.input}
          placeholder="페이지 (예: 10-15, 21)"
          value={pagesStr}
          onChange={(e) => setPagesStr(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          disabled={loading}
        />
        <button style={loading ? s.btnDisabled : s.btn} onClick={submit} disabled={loading}>
          {loading ? "추출 중…" : "+ 세트"}
        </button>
      </div>
      {error && <p style={s.error}>{error}</p>}

      {sets.length === 0 ? (
        <p style={s.empty}>추출 세트가 없습니다.</p>
      ) : (
        <div style={s.list}>
          {sets.map((set) => (
            <div key={set.id} style={s.item}>
              <span style={s.topic}>{set.topic}</span>
              <span style={s.pages}>{set.pages_display}</span>
              <button style={s.del} onClick={() => remove(set.id)} title="삭제">×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", gap: 8 },
  sectionTitle: { fontSize: 14, fontWeight: 700, color: "#222" },
  form: { display: "flex", gap: 6, flexWrap: "wrap" },
  input: { flex: 1, minWidth: 120, padding: "6px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13 },
  btn: { padding: "6px 12px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 4, fontSize: 12, cursor: "pointer" },
  btnDisabled: { padding: "6px 12px", background: "#999", color: "#fff", border: "none", borderRadius: 4, fontSize: 12, cursor: "not-allowed" },
  error: { margin: 0, fontSize: 12, color: "#d32f2f" },
  empty: { fontSize: 13, color: "#999", margin: 0 },
  list: { display: "flex", flexDirection: "column", gap: 4 },
  item: {
    display: "flex", alignItems: "center", gap: 8, padding: "7px 10px",
    background: "#f6f8fa", border: "1px solid #e8e8e8", borderRadius: 6,
  },
  topic: { fontSize: 13, fontWeight: 600, color: "#222", flex: 1 },
  pages: { fontSize: 11, color: "#888" },
  del: { background: "none", border: "none", color: "#b00", fontSize: 16, cursor: "pointer", lineHeight: 1 },
};
