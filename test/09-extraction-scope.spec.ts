import { test, expect } from "@playwright/test";

// ── mock 데이터 ──────────────────────────────────────────────────────────────

const BOOK_ID = "book-001";
const PDF_ID = "pdf-001";

const MOCK_PDF = {
  id: PDF_ID, book_id: BOOK_ID, label: "1부",
  pdf_path: "/docs/ds.pdf", created_at: "2026-10-21T00:00:00Z",
};
const MOCK_BOOK_WITH_PDF = {
  id: BOOK_ID, title: "자료구조 교재", created_at: "2026-10-21T00:00:00Z",
  pdf_files: [MOCK_PDF],
};
const MOCK_EXTRACTION = {
  id: "ext-001", pdf_file_id: PDF_ID, topic: "트리",
  pages: [1, 2, 3, 4, 5], pages_display: "p.1-5", created_at: "2026-10-21T00:00:00Z",
};

// ── E9: PDF 선택 시 추출 세트 / 대화가 독립 2축으로 표시 + 세트 생성 ───────────

test("E9 추출 세트와 대화가 독립 2축으로 표시되고 세트를 생성한다", async ({ page }) => {
  await page.route("**/books", (route) => route.fulfill({ json: [MOCK_BOOK_WITH_PDF] }));
  await page.route(`**/books/${BOOK_ID}/pdfs/${PDF_ID}/extractions`, async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_EXTRACTION });
    else await route.fulfill({ json: [] });
  });
  await page.route(`**/books/${BOOK_ID}/conversations`, (route) => route.fulfill({ json: [] }));

  await page.goto("/");

  // 서재에서 책 펼쳐 PDF 선택
  await page.getByRole("button", { name: /자료구조 교재/ }).click();
  await page.getByText("1부").click();

  // 두 축(추출 세트 / 대화)이 함께 표시됨
  await expect(page.getByText("추출 세트 (주제별 OCR)")).toBeVisible();
  await expect(page.getByRole("button", { name: "+ 새 대화" })).toBeVisible();

  // 추출 세트 생성 (대화 흐름과 독립)
  await page.getByPlaceholder("주제 (예: 자료구조)").fill("트리");
  await page.getByPlaceholder("페이지 (예: 10-15, 21)").fill("1-5");
  await page.getByRole("button", { name: "+ 세트" }).click();

  // 생성된 세트가 추출 세트 목록에 표시됨
  await expect(page.getByText("트리")).toBeVisible();
  await expect(page.getByText("p.1-5")).toBeVisible();
});
