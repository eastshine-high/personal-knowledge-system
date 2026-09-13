import { test, expect } from "@playwright/test";
import { MOCK_SESSION, SESSION_ID, TINY_PNG } from "./fixtures";

test("E6c 실패 재시도: 500 에러 후 폼 재시도 → 성공", async ({ page }) => {
  let callCount = 0;

  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") {
      callCount += 1;
      if (callCount === 1) {
        await route.fulfill({ status: 500, json: { detail: "서버 내부 오류" } });
      } else {
        await route.fulfill({ json: MOCK_SESSION });
      }
    } else {
      await route.continue();
    }
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  await page.goto("/");
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");

  // 첫 시도 → 500 오류
  await page.getByRole("button", { name: "노트 생성" }).click();
  await expect(page.getByText("서버 내부 오류")).toBeVisible();
  await expect(page.getByRole("button", { name: "노트 생성" })).toBeVisible();

  // 재시도 → 성공
  await page.getByRole("button", { name: "노트 생성" }).click();
  await expect(page.getByText("작업 패널")).toBeVisible();
  await expect(page.getByText("셀프 어텐션 메커니즘")).toBeVisible();
});
