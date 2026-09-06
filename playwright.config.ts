import { defineConfig, devices } from '@playwright/test'

/**
 * Harness 표준 Playwright config 템플릿.
 *
 * ⚠️ 사용 전 필수 작업:
 * 1. package.json에 `dev` 스크립트 추가 (Vite면 "dev": "vite", Next면 "dev": "next dev", 등)
 *    아래 webServer.command가 `npm run dev`를 호출하므로 이 스크립트가 없으면 즉시 실패.
 * 2. 프로젝트의 dev server 포트가 5173과 다르면 아래 baseURL과 webServer.url을 함께 수정.
 * 3. UI가 없는 프로젝트(CLI/라이브러리)는 이 파일을 삭제하고 적절한 test runner로 대체.
 *
 * 기본 가정:
 * - 로컬 dev server: http://localhost:5173 (Vite 기본)
 * - 테스트 디렉토리: test/
 * - 브라우저: chromium만 (속도 우선; 필요시 firefox/webkit 추가)
 * - reporter: list (콘솔) + json (`/evaluate` subagent가 파싱)
 *
 * 참조: ~/.claude/harness/principles/04-evaluation-criteria.md
 */
export default defineConfig({
  testDir: './test',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results.json' }],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    cwd: 'frontend',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
