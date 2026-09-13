/** E1~E5 공통 mock 데이터 */

export const SESSION_ID = "test-session-id";
export const NOTE_ID = "note-abc123def456";

export const MOCK_NOTE = {
  id: NOTE_ID,
  title: "셀프 어텐션 메커니즘",
  source: "test.pdf",
  pages: [200],
  topic: "셀프 어텐션",
  created: "2026-09-13",
  body: "셀프 어텐션은 시퀀스 내 각 위치가 다른 모든 위치와 관계를 계산한다.\n\n이를 통해 장거리 의존성을 효과적으로 포착한다.",
  tags: [],
  figures: [],
  markdown: `---\nid: ${NOTE_ID}\ntitle: "셀프 어텐션 메커니즘"\nsource: "test.pdf"\npages: [200]\ntopic: "셀프 어텐션"\ntags: []\ncreated: 2026-09-13\n---\n\n셀프 어텐션은 시퀀스 내 각 위치가 다른 모든 위치와 관계를 계산한다.\n`,
};

export const MOCK_SESSION = {
  session_id: SESSION_ID,
  notes: [MOCK_NOTE],
  events: [{ seq: 0, author: "agent", action: "start", content: "note_count=1" }],
};

export const MOCK_SESSION_AFTER_REFINE = {
  session_id: SESSION_ID,
  notes: [{
    ...MOCK_NOTE,
    body: "- 시퀀스 내 각 위치가 다른 모든 위치와 관계를 계산\n- 장거리 의존성 포착",
  }],
  events: [
    { seq: 0, author: "agent", action: "start", content: "note_count=1" },
    { seq: 1, author: "user", action: "refine", content: "불릿으로 정리해줘" },
  ],
};

export const MOCK_SESSION_AFTER_UNDO = {
  session_id: SESSION_ID,
  notes: [MOCK_NOTE],
  events: [
    { seq: 0, author: "agent", action: "start", content: "note_count=1" },
    { seq: 1, author: "user", action: "refine", content: "불릿으로 정리해줘" },
    { seq: 2, author: "user", action: "revert", content: "seq 0으로 복원" },
  ],
};

/** 1×1 투명 PNG */
export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);
