import { defineConfig, devices } from "@playwright/test";

const PORT = 4174;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // API calls are mocked per test with page.route, so no backend is needed.
    command: `npx vite --port ${PORT} --strictPort`,
    env: { VITE_API_URL: "" },
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
});
