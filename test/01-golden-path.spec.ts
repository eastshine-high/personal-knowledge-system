import { test, expect } from "@playwright/test";
import { MOCK_SESSION, SESSION_ID, TINY_PNG } from "./fixtures";

test("E1 황금 경로: 폼 입력 → 노트 생성 → 패널 표시", async ({ page }) => {
  // --- mock ---
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: MOCK_SESSION });
    } else {
      await route.continue();
    }
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  // --- 입력 폼 ---
  await page.goto("/");
  await expect(page.getByText("PDF 개념 요약 노트")).toBeVisible();

  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");

  await page.getByRole("button", { name: "노트 생성" }).click();

  // --- 워크스페이스로 전환됐는지 ---
  await expect(page.getByText("작업 패널")).toBeVisible();

  // --- 노트 내용 표시 ---
  await expect(page.getByText("셀프 어텐션 메커니즘")).toBeVisible();
  await expect(page.getByText(/셀프 어텐션은 시퀀스 내/)).toBeVisible();

  // --- PDF 뷰어 이미지 로드 ---
  const img = page.locator("img[alt*='페이지']");
  await expect(img).toBeVisible();
});
