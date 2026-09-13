import { test, expect } from "@playwright/test";
import { MOCK_SESSION_TWO_NOTES, SESSION_ID, TINY_PNG } from "./fixtures";

test("E6b 노트 2개 탭 전환: 탭 바 표시 → 두 번째 탭 클릭 → 내용 전환", async ({ page }) => {
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") await route.fulfill({ json: MOCK_SESSION_TWO_NOTES });
    else await route.continue();
  });
  await page.route(`**/sessions/${SESSION_ID}/pages/**`, async (route) => {
    await route.fulfill({ contentType: "image/png", body: TINY_PNG });
  });

  await page.goto("/");
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/test.pdf");
  await page.getByLabel("시작 페이지").fill("200");
  await page.getByLabel("끝 페이지").fill("201");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("셀프 어텐션");
  await page.getByRole("button", { name: "노트 생성" }).click();

  // 탭 바에 두 탭이 표시됨
  await expect(page.getByRole("tab", { name: "셀프 어텐션 메커니즘" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "어텐션 헤드" })).toBeVisible();

  // 첫 번째 탭이 기본 선택 — 첫 노트 내용 표시
  await expect(page.getByText(/셀프 어텐션은 시퀀스 내/)).toBeVisible();

  // 두 번째 탭 클릭 → 두 번째 노트 내용으로 전환
  await page.getByRole("tab", { name: "어텐션 헤드" }).click();
  await expect(page.getByText(/멀티헤드 어텐션은/)).toBeVisible();

  // 첫 번째 노트 내용은 더 이상 보이지 않음
  await expect(page.getByText(/셀프 어텐션은 시퀀스 내/)).not.toBeVisible();
});
