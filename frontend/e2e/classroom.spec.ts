import { expect, test } from "@playwright/test";

// Small valid PNG; uploading identical bytes must produce an exact family.
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAYCAIAAAAUMWhjAAAAJUlEQVR4nGNkaGCgKWCirfGjFoxaMGrBqAWjFoxaMGrBqAXUAgBuowCwfFg98AAAAABJRU5ErkJggg==", "base64");

test("private vault: signup, upload, review, confirm deletion, logout", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("/register");
  await page.getByLabel("Display name").fill("Classroom Student");
  await page.getByLabel("Email address").fill(`${info.project.name}-${Date.now()}@example.com`);
  await page.getByLabel("Password", {exact:true}).fill("test-password-123");
  await page.getByLabel("Invitation code").fill("classroom-test");
  await page.getByRole("button", {name:"Create account"}).click();
  await expect(page).toHaveURL("/");
  await page.goto("/upload");
  await expect(page.getByText(/100 MB RAW\/video/)).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles([
    {name:"original.png", mimeType:"image/png", buffer:png},
    {name:"copy.png", mimeType:"image/png", buffer:png},
  ]);
  await page.getByRole("button", {name:"Upload 2"}).click();
  await expect(page.getByText("Upload complete")).toBeVisible();
  await page.getByRole("link", {name:"View batch"}).click();
  await expect(page.getByText("copy.png", {exact:true})).toBeVisible();
  await expect(page.getByText("Smart analysis is still running")).not.toBeVisible({ timeout: 15000 });
  await page.getByRole("button", {name:/Select exact/i}).click();
  await page.getByRole("button", {name:"Review delete"}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", {name:"Keep images", exact:true}).click();
  await expect(page.getByText("copy.png", {exact:true})).toBeVisible();
  await page.getByRole("button", {name:"Review delete"}).click();
  await page.getByRole("button", {name:"Delete permanently"}).click();
  await expect(page.getByText("copy.png", {exact:true})).not.toBeVisible();
  await page.goto("/gallery");
  await expect(page.getByText("original.png", {exact:true})).toBeVisible();
  await expect(page.getByText("copy.png", {exact:true})).not.toBeVisible();
  await expect(page.getByText("ready", {exact:true})).toBeVisible({timeout:15000});
  // The class presentation must fit a narrow screen without horizontal scrolling.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("gallery.png"), fullPage:true});
  if (info.project.name === "mobile") await page.getByRole("button", {name:"Open navigation"}).click();
  await page.getByRole("button", {name:/Sign out/i}).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/gallery");
  await expect(page).toHaveURL(/\/login$/);
  expect(errors).toEqual([]);
});

test("invalid credentials show a readable message", async ({page}) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("missing@example.com");
  await page.getByLabel("Password", {exact:true}).fill("wrong-password");
  await page.getByRole("button", {name:"Sign in", exact:true}).click();
  await expect(page.getByRole("alert")).toHaveText(/Incorrect email or password/);
  await expect(page).toHaveURL(/\/login$/);
});
