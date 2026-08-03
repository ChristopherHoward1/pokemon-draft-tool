// Browser-drives the multiplayer draft end-to-end against a running stack,
// using playwright-core connected over CDP to a Chrome you launched with
// --remote-debugging-port. No browser download required.
//
//   APP_URL   default http://localhost:5173   (Vite dev server)
//   CDP_URL   default http://127.0.0.1:9222    (Chrome remote-debugging)
//   SHOT_DIR  default $TMPDIR                   (where screenshots are written)
//
// Exits 0 on a fully verified run, non-zero (with the failing step) otherwise.
//
// Two gotchas this script encodes, learned the hard way:
//   - element.innerText returns CSS-*transformed* text, so "On the clock"
//     rendered with text-transform:uppercase reads back as "ON THE CLOCK".
//     Match case-insensitively.
//   - page.waitForFunction(fn, arg, opts) — the 2nd arg is the function
//     argument, not options. Pass `undefined` for arg to reach `opts`.
import os from "node:os";
import { chromium } from "playwright-core";

const APP = (process.env.APP_URL || "http://localhost:5173").replace(/\/$/, "");
const CDP = process.env.CDP_URL || "http://127.0.0.1:9222";
const SHOT_DIR = process.env.SHOT_DIR || os.tmpdir();
const log = (...a) => console.log(...a);

// Poll the "ON THE CLOCK" bar until it names `team`. The board updates one
// React render-tick after the WebSocket broadcast, so a one-shot innerText read
// can catch it stale — wait, don't peek.
async function waitOnClock(page, team, timeout = 8000) {
  const bar = page.locator("text=/ON THE CLOCK/i").first().locator("..");
  const start = Date.now();
  for (;;) {
    const t = await bar.innerText();
    if (new RegExp(team).test(t)) return t;
    if (Date.now() - start > timeout) throw new Error(`[clock] expected ${team}, got: ${t}`);
    await page.waitForTimeout(100);
  }
}

const run = async () => {
  const browser = await chromium.connectOverCDP(CDP);
  const ctx = browser.contexts()[0] || (await browser.newContext());

  // ---- Player A (host): Setup ----
  const a = await ctx.newPage();
  a.on("pageerror", (e) => log("  [A pageerror]", e.message));
  await a.goto(APP, { waitUntil: "networkidle" });
  log("A: loaded Setup —", await a.title());

  // Two teams → a quick full lobby. (The teams input clamps on change.)
  await a.locator('input[type="number"]').first().fill("2");
  await a.getByRole("button", { name: "Create draft room" }).click();
  await a.waitForURL(/\/lobby\//, { timeout: 10000 });
  const code = a.url().split("/lobby/")[1];
  log("A: room created —", code);

  await a.getByPlaceholder("e.g. Team Nova").fill("Alpha");
  await a.getByRole("button", { name: "Join" }).click();
  await a.getByText("you are picking").waitFor({ timeout: 5000 });
  log("A: joined as Alpha (slot 1 / host)");

  // ---- Player B: join same room in a second tab ----
  const b = await ctx.newPage();
  b.on("pageerror", (e) => log("  [B pageerror]", e.message));
  await b.goto(`${APP}/lobby/${code}`, { waitUntil: "networkidle" });
  await b.getByPlaceholder("e.g. Team Nova").fill("Bravo");
  await b.getByRole("button", { name: "Join" }).click();
  await b.getByText("you are picking").waitFor({ timeout: 5000 });
  log("B: joined as Bravo (slot 2)");

  // ---- Host starts once the room is full ----
  const startBtn = a.getByRole("button", { name: "Start Draft" });
  await startBtn.waitFor({ timeout: 5000 });
  if (!(await startBtn.isEnabled())) throw new Error("Start Draft not enabled when full");
  await startBtn.click();
  await a.waitForURL(/\/draft\//, { timeout: 10000 });
  await b.waitForURL(/\/draft\//, { timeout: 10000 });
  log("A+B: navigated to /draft");

  // Snake round 1 → Alpha (slot 1) on the clock.
  const clockBefore = await waitOnClock(a, "Alpha");
  log("A: on the clock →", clockBefore.replace(/\n+/g, " | "));

  // A drafts the first affordable card in the grid.
  const card = a.locator('main div.grid > button:not([disabled])').first();
  const picked = (await card.innerText()).split("\n")[0];
  await card.click();
  log("A: drafted →", picked);

  // Decisive live-broadcast proof: B never clicked, yet B's reconstructed
  // pick-history must go from empty to populated.
  await b.getByText("No picks yet.").waitFor({ state: "hidden", timeout: 8000 });
  log("B: pick history populated — live broadcast reached the non-picking client");

  // Turn advances to Bravo on both boards (poll — the broadcast lands a tick
  // before React repaints).
  for (const [name, page] of [["A", a], ["B", b]]) {
    const clock = await waitOnClock(page, "Bravo");
    log(`${name}: after pick, on the clock →`, clock.replace(/\n+/g, " | "));
  }

  await a.screenshot({ path: `${SHOT_DIR}/draft_A.png` });
  await b.screenshot({ path: `${SHOT_DIR}/draft_B.png` });
  log(`screenshots → ${SHOT_DIR}/draft_A.png, ${SHOT_DIR}/draft_B.png`);

  await browser.close();
  log("\nDRIVE OK — full lobby→draft→pick→broadcast flow verified");
};
run().catch((e) => {
  console.error("DRIVE FAILED:", e.message);
  process.exit(1);
});
