import { defineConfig } from "@playwright/test"
import { mkdirSync, mkdtempSync } from "node:fs"
import path from "node:path"

const directory = import.meta.dirname
const root = path.resolve(directory, "..")
const artifactRoot = process.env.CREMA_E2E_ARTIFACTS ?? path.join(root, "output", "e2e")
mkdirSync(artifactRoot, {recursive: true})
const artifacts = mkdtempSync(path.join(artifactRoot, "run-"))
const database = path.join(artifacts, "espresso.db")
const authDatabase = path.join(artifacts, "auth.db")
const host = process.env.CREMA_E2E_HOST ?? "::1"
const urlHost = host.includes(":") ? `[${host}]` : host
const port = Number(process.env.CREMA_E2E_PORT ?? 8010)
const authPort = Number(process.env.CREMA_E2E_AUTH_PORT ?? 8011)
const baseURL = `http://${urlHost}:${port}`
const authBaseURL = `http://${urlHost}:${authPort}`
const reuseExistingServer = process.env.CREMA_E2E_REUSE === "1" && !process.env.CI

export default defineConfig({
  testDir: "./e2e",
  outputDir: path.join(artifacts, "playwright"),
  preserveOutput: "always",
  fullyParallel: false,
  workers: 1,
  globalTimeout: 120_000,
  timeout: 30_000,
  expect: {timeout: 8_000},
  reporter: "list",
  captureGitInfo: { commit: false, diff: false },
  use: {
    browserName: "chromium",
    viewport: {width: 800, height: 480},
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {name: "local", testIgnore: "auth.spec.ts", use: {baseURL}},
    {name: "session-auth", testMatch: "auth.spec.ts", use: {baseURL: authBaseURL}},
  ],
  webServer: [
    {
      command: `python3 -m devsim --host ${host} --port ${port}`,
      url: `${baseURL}/`,
      cwd: root,
      env: {
        ...process.env,
        CREMA_DB_PATH: database,
        CREMA_BACKUP_DIR: path.join(artifacts, "backups"),
        CREMA_DEV_SIMULATOR: "1",
        CREMA_START_HARDWARE: "0",
        CREMA_AUTH_MODE: "token",
        CREMA_API_TOKEN: "",
        CREMA_CORS_ORIGINS: "",
      },
      reuseExistingServer,
      timeout: 30_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: `python3 -m devsim --host ${host} --port ${authPort}`,
      url: `${authBaseURL}/auth/session`,
      cwd: root,
      env: {
        ...process.env,
        CREMA_DB_PATH: authDatabase,
        CREMA_BACKUP_DIR: path.join(artifacts, "auth-backups"),
        CREMA_DEV_SIMULATOR: "1",
        CREMA_START_HARDWARE: "0",
        CREMA_AUTH_MODE: "session",
        CREMA_SESSION_SECRET: "playwright-session-secret-at-least-32-bytes",
        CREMA_ADMIN_PASSWORD: "correct horse battery",
        CREMA_COOKIE_SECURE: "0",
        CREMA_API_TOKEN: "",
        CREMA_CORS_ORIGINS: "",
      },
      reuseExistingServer,
      timeout: 30_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
})
