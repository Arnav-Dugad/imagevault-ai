import { expect, test, type Page } from "@playwright/test";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAYCAIAAAAUMWhjAAAAJUlEQVR4nGNkaGCgKWCirfGjFoxaMGrBqAWjFoxaMGrBqAXUAgBuowCwfFg98AAAAABJRU5ErkJggg==", "base64");

async function fillRegistration(page: Page, email: string, invitation = "classroom-test") {
  await page.goto("/register");
  await page.getByLabel("Display name").fill("Reliability Student");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("test-password-123");
  await page.getByLabel("Invitation code").fill(invitation);
}

async function register(page: Page, email: string) {
  await fillRegistration(page, email);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL("/");
}

async function openUpload(page: Page) {
  await page.goto("/upload");
  await expect(page.getByText(/100 MB RAW\/video/)).toBeVisible();
}

test("invalid invitation, unsupported files, batch limits and corrupt content are rejected", async ({ page }, info) => {
  const email = `validation-${info.project.name}-${Date.now()}@example.com`;
  await fillRegistration(page, email, "wrong-invitation");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("alert")).toHaveText(/valid invitation code is required/);
  await expect(page).toHaveURL(/\/register$/);

  // The failed attempt must not reserve the email or create an account.
  await page.getByLabel("Invitation code").fill("classroom-test");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL("/");
  await openUpload(page);
  const input = page.locator('input[type="file"]');
  await input.setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not a photo") });
  await expect(page.getByRole("alert")).toHaveText(/supported, non-empty files/);
  await expect(page.getByRole("button", { name: /^Upload \d+$/ })).toHaveCount(0);

  await input.setInputFiles(Array.from({ length: 11 }, (_, index) => ({
    name: `batch-${index}.png`, mimeType: "image/png", buffer: png,
  })));
  await expect(page.getByRole("alert")).toHaveText(/at most 10 files/);
  await expect(page.getByRole("button", { name: /^Upload \d+$/ })).toHaveCount(0);

  // A filename/MIME claim cannot bypass the server's decoder validation.
  await input.setInputFiles({ name: "corrupt.png", mimeType: "image/png", buffer: Buffer.from("broken image bytes") });
  await page.getByRole("button", { name: "Upload 1", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByText("Upload complete")).toHaveCount(0);
  await page.goto("/gallery");
  await expect(page.getByRole("heading", { name: "No images yet" })).toBeVisible();
});

test("interrupted upload keeps a readable error and can be retried without creating a copy", async ({ page }, info) => {
  await register(page, `retry-${info.project.name}-${Date.now()}@example.com`);
  await openUpload(page);
  await page.locator('input[type="file"]').setInputFiles({ name: "retry-photo.png", mimeType: "image/png", buffer: png });
  await page.route("**/api/images/upload", (route) => route.abort("failed"), { times: 1 });
  await page.getByRole("button", { name: "Upload 1", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(/interrupted.*Check the gallery before retrying/);
  await expect(page.getByRole("button", { name: "Upload 1", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Upload 1", exact: true }).click();
  await expect(page.getByText("Upload complete")).toBeVisible();
  await page.goto("/gallery");
  await expect(page.getByText("retry-photo.png", { exact: true })).toHaveCount(1);
  await page.reload();
  await expect(page.getByText("retry-photo.png", { exact: true })).toBeVisible();
});

test("a second account cannot view or delete a private photo, and the owner's library survives refresh", async ({ page, browser }, info) => {
  const suffix = `${info.project.name}-${Date.now()}`;
  await register(page, `owner-${suffix}@example.com`);
  await openUpload(page);
  await page.locator('input[type="file"]').setInputFiles({ name: "owner-private.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Upload 1", exact: true }).click();
  await expect(page.getByText("Upload complete")).toBeVisible();
  await page.goto("/gallery");
  await expect(page.getByText("owner-private.png", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("owner-private.png", { exact: true })).toBeVisible();
  const ownerToken = await page.evaluate(() => localStorage.getItem("imagevault.token"));
  const listing = await page.request.get("/api/images", { headers: { Authorization: `Bearer ${ownerToken}` } });
  expect(listing.status()).toBe(200);
  const { items } = await listing.json();
  expect(items).toHaveLength(1);
  const photoId = items[0].id;

  const otherContext = await browser.newContext({ viewport: page.viewportSize(), baseURL: "http://127.0.0.1:5173" });
  try {
    const otherPage = await otherContext.newPage();
    await register(otherPage, `other-${suffix}@example.com`);
    await otherPage.goto("/gallery");
    await expect(otherPage.getByRole("heading", { name: "No images yet" })).toBeVisible();
    const otherToken = await otherPage.evaluate(() => localStorage.getItem("imagevault.token"));
    const headers = { Authorization: `Bearer ${otherToken}` };
    expect((await otherPage.request.get(`/api/images/${photoId}`, { headers })).status()).toBe(404);
    expect((await otherPage.request.delete(`/api/images/${photoId}?confirm=true`, { headers })).status()).toBe(404);
    expect((await page.request.get(`/api/images/${photoId}`, { headers: { Authorization: `Bearer ${ownerToken}` } })).status()).toBe(200);
    await page.reload();
    await expect(page.getByText("owner-private.png", { exact: true })).toBeVisible();
  } finally {
    await otherContext.close();
  }
});
