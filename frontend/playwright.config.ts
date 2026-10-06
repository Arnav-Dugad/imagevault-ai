import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: process.env.CHROMIUM_EXECUTABLE_PATH ? {
      executablePath: process.env.CHROMIUM_EXECUTABLE_PATH,
      args: ["--no-sandbox", "--disable-gpu"],
    } : undefined,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
  webServer: [
    {
      command: `${process.env.IMAGEVAULT_TEST_PYTHON ?? "../.venv/bin/python"} -m tests.browser_app`,
      cwd: "../backend", url: "http://127.0.0.1:8000/__test_ready", reuseExistingServer: false,
    },
    { command: "npm run preview -- --host 127.0.0.1", url: "http://127.0.0.1:5173", reuseExistingServer: false },
  ],
});
