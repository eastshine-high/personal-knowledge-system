import { test, expect } from "@playwright/test";
import { MOCK_SESSION, SESSION_ID, TINY_PNG, openNoteModal } from "./fixtures";

test("E5 내보내기: 내보내기 버튼 클릭 → 다운로드 URL 요청", async ({ page }) => {
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });
  // export 엔드포인트에 ZIP 응답 mock
  await page.route(`**/sessions/${SESSION_ID}/export`, async (route) => {
    await route.fulfill({
      contentType: "application/zip",
      headers: { "Content-Disposition": 'attachment; filename="notes.zip"' },
      body: Buffer.from("PK"),
    });
  });

  await page.goto("/");
  await openNoteModal(page);
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
  await page.locator("form button[type='submit']").click();

  // 작업 패널이 표시된 후 내보내기 버튼 확인
  await expect(page.getByText("작업 패널")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /내보내기/ }).click();
  const download = await downloadPromise;

  // 다운로드가 시작됐는지 (URL에 /export 포함)
  expect(download.url()).toContain(`/sessions/${SESSION_ID}/export`);
});
