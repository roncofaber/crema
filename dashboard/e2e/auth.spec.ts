import {expect, test} from "@playwright/test"


test("session kiosk signs in, protects actions, and recovers after revocation", async ({page}, testInfo) => {
  await page.goto("/kiosk", {waitUntil: "networkidle"})
  await expect(page.getByRole("heading", {name: "Kiosk sign in"})).toBeVisible()
  await expect(page.getByText("Sign in to enable kiosk controls.")).toBeVisible()
  expect(await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.scrollHeight,
  ])).toEqual([800, 480])
  const controls = await page.locator("button, input").evaluateAll(elements => elements.map(element => {
    const bounds = element.getBoundingClientRect()
    return {top: bounds.top, bottom: bounds.bottom, height: bounds.height}
  }))
  for (const control of controls) {
    expect(control.top).toBeGreaterThanOrEqual(0)
    expect(control.bottom).toBeLessThanOrEqual(480)
    expect(control.height).toBeGreaterThanOrEqual(32)
  }
  await page.screenshot({path: testInfo.outputPath("session-kiosk-login-800x480.png")})
  const protectedAction = await page.request.post("/kiosk/logout", {
    data: {session_started_at: 1},
  })
  expect(protectedAction.status()).toBe(401)

  await page.getByLabel("Administrator password").fill("correct horse battery")
  await page.getByRole("button", {name: "Sign in", exact: true}).click()
  expect((await page.request.post("/dev/simulator/hardware?degraded=false")).ok()).toBeTruthy()
  const armed = await page.request.post("/dev/simulator/state/armed")
  expect(armed.ok()).toBeTruthy()
  await expect(page.getByRole("heading", {name: "alice"})).toBeVisible()
  const optionResponse = page.waitForResponse(response =>
    response.url().endsWith("/kiosk/brew-options") && response.request().method() === "POST",
  )
  await page.getByRole("button", {name: "Single", exact: true}).click()
  expect((await optionResponse).status()).toBe(200)
  await expect(page.getByRole("button", {name: "Single", exact: true})).toHaveClass(/bg-crema-500/)
  const savedOptions = await page.request.get("/dev/simulator/snapshot")
  expect((await savedOptions.json()).shot_type).toBe("single")
  await expect(page.getByRole("button", {name: "Single", exact: true})).toHaveClass(/bg-crema-500/)
  await page.screenshot({path: testInfo.outputPath("session-kiosk-armed-800x480.png")})
  await page.getByRole("button", {name: "Cancel session"}).click()
  await expect(page.getByText("scan to brew")).toBeVisible()

  expect((await page.request.post("/dev/simulator/state/armed")).ok()).toBeTruthy()
  await expect(page.getByRole("heading", {name: "alice"})).toBeVisible()
  expect((await page.request.post("/auth/logout")).ok()).toBeTruthy()
  await page.getByRole("button", {name: "Double", exact: true}).click()
  await expect(page.getByRole("heading", {name: "Kiosk sign in"})).toBeVisible()

  await page.getByLabel("Administrator password").fill("correct horse battery")
  await page.getByRole("button", {name: "Sign in", exact: true}).click()
  await expect(page.getByRole("heading", {name: "alice"})).toBeVisible()
})


test("session login survives reload and logout revokes access", async ({page, context}, testInfo) => {
  const unauthenticated = await page.request.get("/users/")
  expect(unauthenticated.status()).toBe(401)

  await page.goto("/ui/")
  await expect(page.getByRole("heading", {name: "Dashboard sign in"})).toBeVisible()
  await page.getByLabel("Administrator password").fill("incorrect-password")
  await page.getByRole("button", {name: "Sign in", exact: true}).click()
  await expect(page.getByRole("alert")).toContainText("Sign-in failed")

  await page.getByLabel("Administrator password").fill("correct horse battery")
  await page.getByRole("button", {name: "Sign in", exact: true}).click()
  await expect(page.getByRole("heading", {name: "Caffè Cabrini"})).toBeVisible()
  await expect(page.getByRole("heading", {name: "Dashboard sign in"})).toHaveCount(0)

  const cookies = await context.cookies()
  const session = cookies.find(cookie => cookie.name === "crema_session")
  expect(session).toMatchObject({httpOnly: true, secure: false, sameSite: "Strict"})
  const metrics = await page.request.get("/api/metrics")
  expect(metrics.status()).toBe(200)
  expect(await metrics.text()).toContain("crema_up 1")
  await page.screenshot({path: testInfo.outputPath("dashboard-authenticated.png"), fullPage: true})

  await page.reload()
  await expect(page.getByRole("heading", {name: "Caffè Cabrini"})).toBeVisible()
  await page.getByRole("button", {name: "Sign out"}).click()
  await expect(page.getByRole("heading", {name: "Dashboard sign in"})).toBeVisible()

  await page.reload()
  await expect(page.getByRole("heading", {name: "Dashboard sign in"})).toBeVisible()
  expect((await page.request.get("/users/")).status()).toBe(401)
})
