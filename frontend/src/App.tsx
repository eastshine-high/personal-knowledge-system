// Sprint 0 스켈레톤 — 좌우 2분할 레이아웃 자리만 잡는다.
// 실제 기능(PDF 온디맨드 뷰어 · 범위/주제 입력 · 노트 미리보기/편집 · 리파인)은 Sprint 3.
export default function App() {
  return (
    <main style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
      <section style={{ flex: 1, borderRight: '1px solid #ddd', padding: 16 }}>
        <h2>소스 패널</h2>
        <p>PDF 뷰어 · 페이지 범위 · 주제 프롬프트 (Sprint 3)</p>
      </section>
      <section style={{ flex: 1, padding: 16 }}>
        <h2>작업 패널</h2>
        <p>요약 노트 미리보기 · 직접 편집 · 리파인 대화 (Sprint 3)</p>
      </section>
    </main>
  )
}