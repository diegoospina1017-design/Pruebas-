import { test, expect } from "@playwright/test";
import path from "node:path";

const SAMPLE_CSV = path.resolve(__dirname, "../../../samples/mtcars.csv");

test("import dataset, run analysis, add to dashboard, save & reopen project", async ({ page }) => {
  await page.goto("/");

  // Open import dialog from empty state
  await page.getByTestId("empty-import-btn").click();
  const fileInput = page.getByTestId("file-input");
  await fileInput.setInputFiles(SAMPLE_CSV);

  // Wait for preview to appear, then confirm
  await expect(page.getByText("Vista previa", { exact: false })).toBeVisible({ timeout: 10000 });
  await page.getByTestId("confirm-import").click();

  // Grid should be visible
  await expect(page.getByTestId("data-grid")).toBeVisible();

  // Open descriptives dialog
  await page.locator("summary", { hasText: "Análisis" }).click();
  await page.getByTestId("menu-descriptives").click();
  await page.getByTestId("run-analysis").click();

  // Switch to results tab and verify a card was rendered
  await page.getByTestId("tab-results").click();
  await expect(page.getByTestId("result-card").first()).toBeVisible();

  // Add to dashboard
  const addBtn = page.getByRole("button", { name: /Añadir al dashboard/i }).first();
  await addBtn.click();

  // Verify dashboard tile
  await page.getByTestId("tab-dashboard").click();
  await expect(page.locator("text=Histogram").first()).toBeVisible({ timeout: 10000 });
});
