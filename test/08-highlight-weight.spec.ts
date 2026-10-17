import { test, expect } from "@playwright/test";
import { MOCK_SESSION, SESSION_ID, TINY_PNG, openNoteModal } from "./fixtures";

/** 노트 생성 모달을 열고 기본 입력을 채운다. */
async function fillBasics(page: import("@playwright/test").Page) {
  await openNoteModal(page);
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
}

/** POST /sessions 요청 body를 가로채고 성공 응답을 돌려준다. */
async function captureSessionPost(page: import("@playwright/test").Page): Promise<() => any> {
  let body: any = null;
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") {
      body = route.request().postDataJSON();
      await route.fulfill({ json: MOCK_SESSION });
    } else {
      await route.continue();
    }
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, (route) =>
    route.fulfill({ contentType: "image/png", body: TINY_PNG }),
  );
  return () => body;
}

test("E8a 형광펜 가중치 체크 시 use_highlights:true 전송", async ({ page }) => {
  const getBody = await captureSessionPost(page);

  await page.goto("/");
  await fillBasics(page);
  await page.getByLabel("형광펜 가중치 포함").check();
  await page.locator("form button[type='submit']").click();

  await expect(page.getByText("작업 패널")).toBeVisible();
  expect(getBody()?.use_highlights).toBe(true);
});

test("E8b 미체크 시 use_highlights:false (기존 동작)", async ({ page }) => {
  const getBody = await captureSessionPost(page);

  await page.goto("/");
  await fillBasics(page);
  await page.locator("form button[type='submit']").click();

  await expect(page.getByText("작업 패널")).toBeVisible();
  expect(getBody()?.use_highlights).toBe(false);
});
