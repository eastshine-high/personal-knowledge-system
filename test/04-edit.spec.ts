import { test, expect } from "@playwright/test";
import { MOCK_NOTE, MOCK_SESSION, NOTE_ID, SESSION_ID, TINY_PNG, openNoteModal } from "./fixtures";

test("E4 직접 편집: 편집 저장 → UI에 반영", async ({ page }) => {
  const EDITED_NOTE = { ...MOCK_NOTE, body: "직접 수정한 본문 내용입니다." };

  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/notes/${NOTE_ID}/edit`, async (route) => {
    await route.fulfill({ json: EDITED_NOTE });
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  await page.goto("/");
  await openNoteModal(page);
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
  await page.locator("form button[type='submit']").click();

  // 편집 모드 진입
  await page.getByRole("button", { name: "편집" }).click();
  await expect(page.getByRole("button", { name: "저장" })).toBeVisible();

  // 본문 수정 (body textarea — RefineChat textarea와 구분)
  const textarea = page.locator("textarea").first();
  await textarea.fill("직접 수정한 본문 내용입니다.");

  // 저장
  await page.getByRole("button", { name: "저장" }).click();

  // 편집 모드 닫히고 수정된 내용 표시
  await expect(page.getByRole("button", { name: "편집" })).toBeVisible();
  await expect(page.getByText("직접 수정한 본문 내용입니다.")).toBeVisible();
});
