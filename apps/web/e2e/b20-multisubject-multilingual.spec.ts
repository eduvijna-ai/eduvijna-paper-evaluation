import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B20 mock multi-subject and multilingual", () => {
  test("upload exposes language/script fields", async ({ page }) => {
    await openAuthed(page, "/submissions/upload");
    await expect(page.getByTestId("upload-language-code")).toBeVisible();
    await expect(page.getByTestId("upload-script-code")).toBeVisible();
  });

  test("mathematics assessment still shows math-eligible subject profile", async ({
    page,
  }) => {
    await openAuthed(page, "/assessments/assess-demo-001");
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(
      /Mathematics/i,
    );
    await expect(page.getByTestId("assessment-math-verification")).toContainText(
      /Eligible/i,
    );
  });

  test("physics assessment shows non-math profile", async ({ page }) => {
    await openAuthed(page, "/assessments/assess-b20-physics");
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(
      /Physics/i,
    );
    await expect(page.getByTestId("assessment-math-verification")).toContainText(
      /Not eligible/i,
    );
  });

  test("descriptive assessment shows structured descriptive profile", async ({
    page,
  }) => {
    await openAuthed(page, "/assessments/assess-b20-descriptive");
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(
      /Structured descriptive/i,
    );
  });

  test("hindi transcription keeps original text distinct from translation", async ({
    page,
  }) => {
    await openAuthed(page, "/submissions/sub-b20-hindi/transcription");
    await expect(page.getByTestId("transcription-review-page")).toBeVisible();
    await expect(page.getByTestId("transcription-language-code")).toHaveText("hi");
    await expect(page.getByTestId("transcription-script-code")).toHaveText("Deva");
    await expect(page.getByTestId("transcription-language-source")).toContainText(
      /PROVIDED/i,
    );
    await expect(page.getByTestId("transcription-original-text").first()).toContainText(
      "हिंदी में हल",
    );
    await expect(page.getByTestId("transcription-translation")).toBeVisible();
    await expect(page.getByTestId("transcription-translation")).toContainText(
      "Solution in Hindi",
    );
    await expect(page.getByTestId("transcription-transliteration")).toBeVisible();
    const original = await page
      .getByTestId("transcription-original-text")
      .first()
      .textContent();
    const translation = await page.getByTestId("transcription-translation").textContent();
    expect(original).toBeTruthy();
    expect(translation).toBeTruthy();
    expect(translation).not.toEqual(original);
  });

  test("unsupported language shows fail-closed block and does not auto-progress", async ({
    page,
  }) => {
    await openAuthed(page, "/submissions/sub-b20-unsupported/transcription");
    await expect(page.getByTestId("transcription-language-state")).toContainText(
      /Unsupported/i,
    );
    await expect(page.getByTestId("transcription-automation-block")).toContainText(
      "LANGUAGE_UNSUPPORTED",
    );
    await expect(page.getByTestId("transcription-automated-notice")).toHaveCount(0);
  });

  test("physics transcription workspace is not math-labeled", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-b20-physics/transcription");
    await expect(page.getByTestId("transcription-subject-profile")).toContainText(
      /Physics/i,
    );
    await expect(page.getByTestId("transcription-original-text").first()).toContainText(
      /Newton/i,
    );
  });
});
