import { test, expect } from "@playwright/test";
import { MOCK_SESSION, MOCK_SESSION_AFTER_REFINE, SESSION_ID, TINY_PNG, openNoteModal } from "./fixtures";

test("E2 리파인: instruction 입력 → 노트 갱신 → events 패널에 지시 표시", async ({ page }) => {
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/refine`, async (route) => {
    await route.fulfill({ json: MOCK_SESSION_AFTER_REFINE });
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

  // 리파인 instruction 입력
  await page.getByPlaceholder(/지시 입력/).fill("불릿으로 정리해줘");
  await page.getByRole("button", { name: "전송" }).click();

  // 노트 본문이 불릿으로 갱신됐는지 확인
  await expect(page.getByText(/시퀀스 내 각 위치가/)).toBeVisible();

  // events 히스토리에 지시가 말풍선으로 표시됐는지
  await expect(page.getByText("불릿으로 정리해줘")).toBeVisible();
});
