import { test, expect } from "@playwright/test";
import {
  MOCK_NOTE,
  MOCK_SESSION,
  MOCK_SESSION_AFTER_REFINE,
  MOCK_SESSION_AFTER_UNDO,
  SESSION_ID,
  TINY_PNG,
} from "./fixtures";

test("E3 undo: refine 후 undo → 이전 노트 복원", async ({ page }) => {
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/refine`, async (route) => {
    await route.fulfill({ json: MOCK_SESSION_AFTER_REFINE });
  });
  await page.route(`**/sessions/${SESSION_ID}/undo`, async (route) => {
    await route.fulfill({ json: MOCK_SESSION_AFTER_UNDO });
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  await page.goto("/");
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("200");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
  await page.getByRole("button", { name: "노트 생성" }).click();

  // refine
  await page.getByPlaceholder(/지시 입력/).fill("불릿으로 정리해줘");
  await page.getByRole("button", { name: "전송" }).click();
  await expect(page.getByText("불릿으로 정리해줘")).toBeVisible();

  // undo
  await page.getByRole("button", { name: /undo/ }).click();

  // 원래 노트 본문으로 복원됐는지
  await expect(page.getByText(/셀프 어텐션은 시퀀스 내/)).toBeVisible();

  // events에 revert 표시
  await expect(page.getByText("되돌림")).toBeVisible();
});
