import { expect, test, type Page } from "@playwright/test"

async function setState(page: Page, name: string) {
  const response = await page.request.post(`/dev/simulator/state/${name}`)
  expect(response.ok(), `${name}: ${response.status()} ${await response.text()}`).toBeTruthy()
  if (name === "idle") await expect(page.getByText("scan to brew")).toBeVisible()
  if (name === "armed") await expect(page.getByRole("heading", { name: "alice" })).toBeVisible()
  if (name === "brewing") await expect(page.getByText(/^×\d+$/)).toBeVisible()
  if (name === "anon_brew") await expect(page.getByText("Scan now to claim this brew")).toBeVisible()
}

async function assertLayout(page: Page) {
  const layout = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll("button")]
      .filter(button => {
        const rect = button.getBoundingClientRect()
        const style = getComputedStyle(button)
        return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden"
      })
      .map(button => {
        const rect = button.getBoundingClientRect()
        return {
          name: button.textContent || button.getAttribute("aria-label"),
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        }
      })
    return {
      viewport: [innerWidth, innerHeight],
      document: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
      body: [document.body.scrollWidth, document.body.scrollHeight],
      buttons,
    }
  })
  expect(layout.viewport).toEqual([800, 480])
  expect(layout.document).toEqual([800, 480])
  expect(layout.body[0]).toBeLessThanOrEqual(800)
  expect(layout.body[1]).toBeLessThanOrEqual(480)
  for (const button of layout.buttons) {
    expect(button.width, `${button.name} width`).toBeGreaterThanOrEqual(32)
    expect(button.height, `${button.name} height`).toBeGreaterThanOrEqual(32)
    expect(button.left, `${button.name} left`).toBeGreaterThanOrEqual(0)
    expect(button.top, `${button.name} top`).toBeGreaterThanOrEqual(0)
    expect(button.right, `${button.name} right`).toBeLessThanOrEqual(800)
    expect(button.bottom, `${button.name} bottom`).toBeLessThanOrEqual(480)
  }
}

test("all kiosk states fit the production viewport and interactions recover", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", error => errors.push(error.message))
  await page.goto("/kiosk", { waitUntil: "networkidle" })

  await setState(page, "idle")
  await assertLayout(page)
  await page.screenshot({ path: testInfo.outputPath("kiosk-idle-800x480.png") })

  await setState(page, "armed")
  await assertLayout(page)
  await page.getByRole("button", { name: "Single", exact: true }).click()
  await expect(page.getByRole("button", { name: "Single", exact: true })).toHaveClass(/bg-crema-500/)
  await page.getByRole("button", { name: "On", exact: true }).click()
  await expect(page.getByRole("button", { name: "On", exact: true })).toHaveClass(/bg-crema-500/)

  await page.route("**/kiosk/brew-options", route => route.abort())
  await page.getByRole("button", { name: "Double", exact: true }).click()
  await expect(page.getByRole("alert")).toContainText("Could not save brew options")
  await expect(page.getByRole("button", { name: "Single", exact: true })).toHaveClass(/bg-crema-500/)
  await page.unroute("**/kiosk/brew-options")

  await page.route("**/kiosk/logout", route => route.abort())
  await page.getByRole("button", { name: "Cancel session" }).click()
  await expect(page.getByRole("alert")).toContainText("Could not end the session")
  await page.unroute("**/kiosk/logout")
  await page.getByRole("button", { name: "Cancel session" }).click()
  await expect(page.getByText("scan to brew")).toBeVisible()

  await setState(page, "brewing")
  await assertLayout(page)
  await setState(page, "anon_brew")
  await assertLayout(page)

  await setState(page, "summary")
  await expect(page.getByText("Grazie,")).toBeVisible()
  await assertLayout(page)

  await setState(page, "brewing")
  const rating = await page.request.post("/dev/simulator/state/rating")
  expect(rating.ok()).toBeTruthy()
  await expect(page.getByRole("heading", { name: "How was that one?" })).toBeVisible()
  await assertLayout(page)

  await page.route("**/kiosk/rate", route => route.abort())
  await page.getByRole("button", { name: "Rate 4 out of 5" }).click()
  await expect(page.getByRole("alert")).toContainText("Rating not saved")
  await assertLayout(page)
  await page.unroute("**/kiosk/rate")
  await page.getByRole("button", { name: "Retry rating" }).click()
  await expect(page.getByRole("heading", { name: "How was that one?" })).toHaveCount(0)

  await page.request.post("/dev/simulator/disconnect")
  await expect(page.getByText("Kiosk unavailable")).toBeVisible()
  await expect(page.locator('[data-connection-state="reconnecting"]')).toBeVisible()
  await assertLayout(page)
  await page.screenshot({ path: testInfo.outputPath("kiosk-reconnecting-800x480.png") })
  await page.request.post("/dev/simulator/restore")
  await expect(page.locator('[data-connection-state="live"]')).toBeVisible()
  await setState(page, "armed")
  await page.request.post("/dev/simulator/hardware?degraded=true")
  await expect(page.getByRole("status")).toContainText("Scanner offline")
  await expect(page.getByRole("status")).toContainText("Sensor offline")
  await assertLayout(page)

  await page.request.post("/dev/simulator/hardware?degraded=false&missing_samples=true")
  await expect(page.getByRole("status")).toContainText("Sensor stale")
  await assertLayout(page)
  await page.screenshot({ path: testInfo.outputPath("kiosk-hardware-stale-800x480.png") })
  expect(errors).toEqual([])
})

test("a delayed logout cannot end or disable a replacement session", async ({ page }) => {
  await page.goto("/kiosk", { waitUntil: "networkidle" })
  await setState(page, "armed")

  let releaseLogout: (() => void) | undefined
  const delayed = new Promise<void>(resolve => { releaseLogout = resolve })
  let intercepted = 0
  await page.route("**/kiosk/logout", async route => {
    intercepted += 1
    await delayed
    await route.continue()
  })
  await page.getByRole("button", { name: "Cancel session" }).click()
  await expect(page.getByRole("button", { name: "Ending session..." })).toBeDisabled()
  expect(intercepted).toBe(1)

  await setState(page, "handoff")
  await expect(page.getByRole("heading", { name: "bob" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Cancel session" })).toBeEnabled()
  releaseLogout?.()

  await expect(page.getByRole("heading", { name: "bob" })).toBeVisible()
  await expect(page.getByRole("alert")).toHaveCount(0)
  await page.unroute("**/kiosk/logout")
  await page.getByRole("button", { name: "Cancel session" }).click()
  await expect(page.getByText("scan to brew")).toBeVisible()
})

test("audio opt-in and quiet hours persist locally", async ({ page }, testInfo) => {
  await page.goto("/kiosk", { waitUntil: "networkidle" })
  await expect(page.getByRole("button", { name: "Sound off" })).toHaveAttribute("aria-pressed", "false")
  await page.getByRole("button", { name: "Audio settings" }).click()
  await expect(page.getByRole("dialog", { name: "Audio feedback" })).toBeVisible()
  await page.getByLabel("Enable feedback cues").check()
  await expect(page.getByLabel("Use quiet hours")).toBeChecked()
  await page.getByLabel("Quiet hours start").fill("23:30")
  await page.getByLabel("Quiet hours end").fill("06:45")
  await assertLayout(page)
  await page.screenshot({ path: testInfo.outputPath("kiosk-audio-quiet-hours-800x480.png") })
  await page.getByRole("button", { name: "Done" }).click()
  await expect(page.getByRole("button", { name: "Sound on" })).toHaveAttribute("aria-pressed", "true")

  await page.reload({ waitUntil: "networkidle" })
  await expect(page.getByRole("button", { name: "Sound on" })).toHaveAttribute("aria-pressed", "true")
  await page.getByRole("button", { name: "Audio settings" }).click()
  await expect(page.getByLabel("Quiet hours start")).toHaveValue("23:30")
  await expect(page.getByLabel("Quiet hours end")).toHaveValue("06:45")
  await page.getByLabel("Use quiet hours").uncheck()
  await page.reload({ waitUntil: "networkidle" })
  await page.getByRole("button", { name: "Audio settings" }).click()
  await expect(page.getByLabel("Use quiet hours")).not.toBeChecked()
  await page.getByLabel("Enable feedback cues").uncheck()
  await page.getByRole("button", { name: "Done" }).click()
  await expect(page.getByRole("button", { name: "Sound off" })).toHaveAttribute("aria-pressed", "false")
})
