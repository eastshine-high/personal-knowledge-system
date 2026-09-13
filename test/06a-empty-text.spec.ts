import { test, expect } from "@playwright/test";

test("E6a 텍스트 0건: 422 응답 → 폼에 오류 메시지, 워크스페이스 미전환", async ({ page }) => {
  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 422, json: { detail: "요약할 텍스트가 없습니다." } });
    } else {
      await route.continue();
    }
  });

  await page.goto("/");
  await page.getByPlaceholder("/path/to/document.pdf").fill("/path/to/blank.pdf");
  await page.getByLabel("시작 페이지").fill("5");
  await page.getByLabel("끝 페이지").fill("5");
  await page.getByPlaceholder("예: 셀프 어텐션 메커니즘").fill("테스트");
  await page.getByRole("button", { name: "노트 생성" }).click();

  // 오류 메시지 표시
  await expect(page.getByText("요약할 텍스트가 없습니다.")).toBeVisible();

  // 폼이 유지됨 (작업 패널로 전환되지 않음)
  await expect(page.getByRole("button", { name: "노트 생성" })).toBeVisible();
  await expect(page.getByText("작업 패널")).not.toBeVisible();
});
