import { defineConfig, devices } from "@playwright/test";

// next build로 만든 out/을 정적 서버로 띄워 휴대폰 화면 크기로 검사한다. API는 테스트 안에서 가짜 응답으로 가로챔
export default defineConfig({
  testDir: "./e2e",
  use: { ...devices["Pixel 7"], baseURL: "http://localhost:3100" },
  webServer: {
    command: "npx serve out -l 3100",
    url: "http://localhost:3100",
    reuseExistingServer: !process.env.CI,
  },
});
