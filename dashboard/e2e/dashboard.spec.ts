import {expect, test} from "@playwright/test"


test("recent filters work in a horizontal toolbar at 375px", async ({page}, testInfo) => {
  await page.setViewportSize({width: 375, height: 812})
  const created = await page.request.post("/dev/simulator/state/rating")
  expect(created.ok()).toBeTruthy()
  await page.goto("/ui/")

  const recent = page.getByRole("region", {name: "Recent brews"})
  const toolbar = recent.getByRole("region", {name: "Brew filters"})
  await expect(recent.getByRole("cell", {name: /^alice/}).first()).toBeVisible()
  const dimensions = await toolbar.evaluate(element => ({
    client: element.clientWidth,
    scroll: element.scrollWidth,
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(dimensions.scroll).toBeGreaterThan(dimensions.client)
  expect(dimensions.document).toBe(dimensions.viewport)
  await toolbar.evaluate(element => {element.scrollLeft = element.scrollWidth})
  await expect.poll(() => toolbar.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)

  await recent.getByLabel("User").fill("nobody")
  await expect(recent.getByText("No records match these filters.")).toBeVisible()
  await recent.getByLabel("User").fill("alice")
  await recent.getByLabel("Records").selectOption("all")
  await recent.getByLabel("Shot").selectOption("double")
  await recent.getByLabel("Decaf").selectOption("no")
  const today = await page.evaluate(() => {
    const date = new Date()
    const month = String(date.getMonth() + 1).padStart(2, "0")
    const day = String(date.getDate()).padStart(2, "0")
    return `${date.getFullYear()}-${month}-${day}`
  })
  await recent.getByLabel("From", {exact: true}).fill(today)
  await recent.getByLabel("To", {exact: true}).fill(today)
  await expect(recent.getByRole("cell", {name: /^alice/}).first()).toBeVisible()
  const result = recent.getByRole("cell", {name: "alice double", exact: true})
  await expect(result.getByText("double", {exact: true})).toBeVisible()
  await expect(recent.getByRole("cell", {name: "brew", exact: true})).toBeVisible()
  await page.screenshot({path: testInfo.outputPath("mobile-recent-filters-375.png"), fullPage: true})

  await recent.getByLabel("Records").selectOption("noise")
  await expect(recent.getByText("No records match these filters.")).toBeVisible()
  await page.getByRole("button", {name: "Reset filters"}).click()
  await expect(recent.getByLabel("Records")).toHaveValue("brew")
  await expect(recent.getByLabel("User")).toHaveValue("")
  await expect(recent.getByRole("cell", {name: /^alice/}).first()).toBeVisible()
})
