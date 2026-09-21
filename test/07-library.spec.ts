import { test, expect } from "@playwright/test";
import { MOCK_SESSION, SESSION_ID, TINY_PNG, openNoteModal } from "./fixtures";

// ── 서재/대화 mock 데이터 ─────────────────────────────────────────────────────

const BOOK_ID = "book-001";
const PDF_ID = "pdf-001";
const CONV_ID = "conv-001";
const MSG_ID = "msg-001";

const MOCK_BOOK = {
  id: BOOK_ID,
  title: "트랜스포머 완전정복",
  created_at: "2026-09-21T00:00:00Z",
  pdf_files: [],
};

const MOCK_PDF = {
  id: PDF_ID,
  book_id: BOOK_ID,
  label: "1부",
  pdf_path: "/docs/transformer.pdf",
  created_at: "2026-09-21T00:00:00Z",
};

const MOCK_BOOK_WITH_PDF = { ...MOCK_BOOK, pdf_files: [MOCK_PDF] };

const MOCK_CONV = {
  id: CONV_ID,
  book_id: BOOK_ID,
  pdf_file_id: PDF_ID,
  pages: [10, 11, 12, 13, 14, 15, 21],
  pages_display: "p.10-15, 21",
  title: null,
  created_at: "2026-09-21T00:00:00Z",
};

const MOCK_ASSISTANT_MSG = {
  id: MSG_ID,
  conversation_id: CONV_ID,
  role: "assistant",
  content: "[Mock 응답] 어텐션 메커니즘에 대해 답변합니다.",
  created_at: "2026-09-21T00:00:00Z",
};

const MOCK_CHAT_RESP = {
  conversation: MOCK_CONV,
  message: MOCK_ASSISTANT_MSG,
};

// ── S5a: 책+PDF 등록 → 서재 트리에 표시 ─────────────────────────────────────

test("S5a 서재 등록: 책 추가 → PDF 추가 → 트리 표시", async ({ page }) => {
  let bookCreated = false;

  await page.route("**/books", async (route) => {
    if (route.request().method() === "POST") {
      bookCreated = true;
      await route.fulfill({ json: MOCK_BOOK });
    } else {
      await route.fulfill({ json: bookCreated ? [MOCK_BOOK] : [] });
    }
  });
  await page.route(`**/books/${BOOK_ID}/pdfs`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: MOCK_PDF });
    } else {
      await route.continue();
    }
  });

  await page.goto("/");

  // 책 추가
  await page.getByRole("button", { name: "+ 책 추가" }).click();
  await page.getByPlaceholder("책 제목").fill("트랜스포머 완전정복");
  await page.getByRole("button", { name: "추가" }).click();

  // 책 제목이 서재에 표시됨 (submitBook이 자동으로 펼침)
  await expect(page.getByText("트랜스포머 완전정복")).toBeVisible();

  // PDF 추가 (책은 이미 자동 펼쳐짐)
  await page.getByRole("button", { name: "+ PDF 추가" }).click();
  await page.getByPlaceholder("레이블 (예: 1부)").fill("1부");
  await page.getByPlaceholder("PDF 경로").fill("/docs/transformer.pdf");
  await page.getByRole("button", { name: "추가", exact: true }).click();

  // PDF 레이블이 트리에 표시됨
  await expect(page.getByText("1부")).toBeVisible();
});

// ── S5b: 새 대화 시작 → ChatPanel 전환 ──────────────────────────────────────

test("S5b 새 대화: PDF 선택 → 페이지 입력 → ChatPanel 표시", async ({ page }) => {
  await page.route("**/books", async (route) => {
    await route.fulfill({ json: [MOCK_BOOK_WITH_PDF] });
  });
  await page.route(`**/books/${BOOK_ID}/conversations`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: MOCK_CONV });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.route(`**/conversations/${CONV_ID}/messages`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/");

  // 서재에서 책 펼쳐 PDF 선택
  await page.getByRole("button", { name: /트랜스포머 완전정복/ }).click();
  await page.getByText("1부").click();

  // 새 대화 버튼 클릭
  await page.getByRole("button", { name: "+ 새 대화" }).click();

  // 페이지 범위 입력
  await page.getByPlaceholder("예: 10-15, 21").fill("10-15, 21");
  await page.getByRole("button", { name: "대화 시작" }).click();

  // ChatPanel로 전환됐는지 확인
  await expect(page.getByText("새 대화")).toBeVisible();
  await expect(page.getByText("p.10-15, 21")).toBeVisible();
  await expect(page.getByPlaceholder(/메시지 입력/)).toBeVisible();
});

// ── S5c: 대화 계속 — 메시지 전송 → 응답 수신 ─────────────────────────────────

test("S5c 대화 계속: 메시지 전송 → Mock 응답 표시", async ({ page }) => {
  await page.route("**/books", async (route) => {
    await route.fulfill({ json: [MOCK_BOOK_WITH_PDF] });
  });
  await page.route(`**/books/${BOOK_ID}/conversations`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: MOCK_CONV });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.route(`**/conversations/${CONV_ID}/messages`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: MOCK_CHAT_RESP });
    } else {
      await route.fulfill({ json: [] });
    }
  });

  await page.goto("/");

  // PDF 선택 → 새 대화 → 시작
  await page.getByRole("button", { name: /트랜스포머 완전정복/ }).click();
  await page.getByText("1부").click();
  await page.getByRole("button", { name: "+ 새 대화" }).click();
  await page.getByPlaceholder("예: 10-15, 21").fill("10-15, 21");
  await page.getByRole("button", { name: "대화 시작" }).click();

  // 메시지 입력 + 전송
  await page.getByPlaceholder(/메시지 입력/).fill("어텐션 메커니즘이란?");
  await page.getByRole("button", { name: "전송" }).click();

  // 사용자 메시지 표시
  await expect(page.getByText("어텐션 메커니즘이란?")).toBeVisible();

  // Mock 응답 표시
  await expect(page.getByText("[Mock 응답] 어텐션 메커니즘에 대해 답변합니다.")).toBeVisible();
});

// ── S5d: regression — 서재가 있을 때도 노트 생성 모달이 정상 동작 ─────────────

test("S5d 노트 생성 regression: 서재 있을 때도 모달로 노트 생성 가능", async ({ page }) => {
  await page.route("**/books", async (route) => {
    await route.fulfill({ json: [MOCK_BOOK_WITH_PDF] });
  });
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  await page.goto("/");

  // 서재가 표시되는지 확인
  await expect(page.getByText("트랜스포머 완전정복")).toBeVisible();

  // 노트 생성 모달 열기
  await openNoteModal(page);
  await expect(page.getByText("PDF 개념 요약 노트")).toBeVisible();

  // 폼 작성 + 제출
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
  await page.locator("form button[type='submit']").click();

  // 노트 세션으로 전환됐는지
  await expect(page.getByText("작업 패널")).toBeVisible();
  await expect(page.getByText("셀프 어텐션 메커니즘")).toBeVisible();
});
