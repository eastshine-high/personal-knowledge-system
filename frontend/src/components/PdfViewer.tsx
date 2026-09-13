import { useState } from "react";
import { pageImageUrl } from "../api";

interface Props {
  sessionId: string;
  pages: number[];
}

export default function PdfViewer({ sessionId, pages }: Props) {
  const [idx, setIdx] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  if (pages.length === 0) {
    return <p style={{ color: "#999", fontSize: 13 }}>추출된 페이지 없음</p>;
  }

  const pageNum = pages[idx];

  const prev = () => { setIdx((i) => Math.max(0, i - 1)); setLoaded(false); setError(false); };
  const next = () => { setIdx((i) => Math.min(pages.length - 1, i + 1)); setLoaded(false); setError(false); };

  return (
    <div style={styles.container}>
      <div style={styles.nav}>
        <button style={styles.navBtn} onClick={prev} disabled={idx === 0}>◀</button>
        <span style={styles.pageLabel}>p.{pageNum} ({idx + 1} / {pages.length})</span>
        <button style={styles.navBtn} onClick={next} disabled={idx === pages.length - 1}>▶</button>
      </div>

      <div style={styles.imageWrap}>
        {!loaded && !error && <p style={styles.hint}>로딩 중…</p>}
        {error && <p style={styles.errorHint}>이미지를 불러올 수 없습니다.</p>}
        <img
          key={pageNum}
          src={pageImageUrl(sessionId, pageNum)}
          alt={`페이지 ${pageNum}`}
          style={{ ...styles.image, display: loaded ? "block" : "none" }}
          onLoad={() => setLoaded(true)}
          onError={() => { setError(true); setLoaded(false); }}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: "flex", flexDirection: "column", gap: 8, height: "100%" },
  nav: { display: "flex", alignItems: "center", gap: 12 },
  navBtn: {
    padding: "4px 10px",
    border: "1px solid #ccc",
    borderRadius: 4,
    background: "#fff",
    cursor: "pointer",
    fontSize: 13,
  },
  pageLabel: { fontSize: 13, color: "#555" },
  imageWrap: {
    flex: 1,
    border: "1px solid #e0e0e0",
    borderRadius: 4,
    background: "#f9f9f9",
    overflow: "auto",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "center",
  },
  image: { maxWidth: "100%", display: "block" },
  hint: { color: "#999", fontSize: 13, alignSelf: "center" },
  errorHint: { color: "#d32f2f", fontSize: 13, alignSelf: "center" },
};
