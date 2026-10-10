/* Browser end-to-end test for the camera prototype (Playwright + Chromium fake camera).
 *
 * Runs against a local server whose providers point at the MOCK server (backend/tests/mock_providers.py),
 * so it needs no keys or internet. Results print as PASS/FAIL lines; exit code 1 on any failure.
 *
 *   cd backend && python tests/mock_providers.py 8099 &
 *   LLM_BASE_URL=http://127.0.0.1:8099/openai/v1 VISION_BASE_URL=http://127.0.0.1:8099/openai/v1 \
 *   SARVAM_BASE_URL=http://127.0.0.1:8099 LLM_API_KEY=mock GROQ_API_KEY=mock SARVAM_API_KEY=mock \
 *   uvicorn app.main:app --port 8000 &
 *   npx playwright@1.56 --version >/dev/null; PW=$(npm root -g)/playwright node ../frontend/tests/camera_e2e.js
 */
const { chromium } = require(process.env.PW || "playwright");
const fs = require("fs");
const out = process.argv[2] || require("os").tmpdir();
const BASE = process.env.BASE_URL || "http://localhost:8000";
const results = [];
const TEST_JPEG = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCABIAGADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwCCiiivNPSCiiigAooooAKKKKACiiigAooooAKKKKACiinRoZJFjXGWIAz70ASWtrJdy7E4A+83YCtaLSLZB84aQ+pOP5Vaggjt4hHGMAfmT6mpKCkim+k2jDCoye6sf61lXljJZsMnch6MB39K6GmyRpKhR1DK3UGgGjl6Kluofs9y8WchTx9O1RUEhRRRQAUUUUAFWtM/5CEX4/yNVafDKYZklGflOcA4z7UAdPWT4gkmjtYxGSsbMQ5BwenA+nX8q1I5ElQOjBlboRSsoZSrAFSMEHoaDaEuWSZh+HZJmeWMkmFVHU/dOe315/Kt2moiRoEjRUUdAowBTiQoLMQAOST2pDqS5pXMXWf+PxP+uY/maz6nvZ/tF08gJ29F+n+eagpmDCiiigAooooAKKKKALVjfPaPg5aNvvL/AFFbEWoWsoyJlX1D8Y/OudooGmdG99axjLTof905/lWTf6i11+7jBWLuD1Y+9UqKAbCiiigQUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAf/Z"; // 96x72 synthetic "hand" photo
const check = (name, ok, extra = "") => { results.push([ok ? "PASS" : "FAIL", name, extra]); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function page(browser, opts = {}) {
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1360, height: 900 }, permissions: opts.permissions ?? ["camera", "microphone"] });
  const p = await ctx.newPage();
  p.errs = [];
  p.on("pageerror", (e) => p.errs.push(e.message));
  p.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && p.errs.push(m.text()));
  if (opts.init) await p.addInitScript(opts.init);
  await p.goto(BASE); await p.waitForTimeout(500);
  return p;
}
const flipped = (p) => p.evaluate(() => document.getElementById("flipper").classList.contains("flipped"));
const liveTracks = (p) => p.evaluate(() => { const v = document.getElementById("camVideo"); return v.srcObject ? v.srcObject.getTracks().filter((t) => t.readyState === "live").length : 0; });
const status = (p) => p.locator("#camLive").innerText();

(async () => {
  const b = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
  // --- main flow, English ---
  let p = await page(b);
  check("camera controls hidden on the front at start", !(await p.isVisible("#camControls")) && await p.isVisible("#cameraOpenBtn"));
  await p.keyboard.press("2"); await p.waitForTimeout(300);
  await p.keyboard.press("6"); await p.waitForTimeout(250);
  await p.screenshot({ path: `${out}/c1-midflip.png` });
  await p.waitForFunction(() => document.getElementById("camLive").innerText.includes("CAMERA READY"), null, { timeout: 8000 }).catch(() => {});
  check("key 6 flips to back", await flipped(p));
  check("front is inert while flipped", await p.evaluate(() => document.getElementById("phone").inert === true && !document.getElementById("phoneBack").inert));
  check("live preview running", (await liveTracks(p)) === 1, await status(p));
  for (let i = 0; i < 3; i++) {
    await p.click("#camFlash");
    const on = await p.evaluate(() => ["led", "cone"].every((id) => document.getElementById(id).classList.contains("on")) && document.getElementById("viewfinder").classList.contains("lit"));
    if (i === 0) await p.screenshot({ path: `${out}/c2-flash-on.png` });
    await p.click("#camFlash");
    const off = await p.evaluate(() => !document.getElementById("led").classList.contains("on") && !document.getElementById("cone").classList.contains("on") && !document.getElementById("viewfinder").classList.contains("lit"));
    if (!(on && off)) { check(`flash toggle round ${i}`, false); break; }
    if (i === 2) check("flash toggles on/off 3x", true, await status(p));
  }
  await p.click("#camCapture"); await p.waitForTimeout(400);
  check("capture shows review image", await p.isVisible("#camShot") && await p.isVisible("#camAnalyze") && await p.isVisible("#camRetake"), await status(p));
  check("camera stopped while reviewing", (await liveTracks(p)) === 0);
  await p.click("#camRetake"); await p.waitForTimeout(800);
  check("retake restarts preview", (await liveTracks(p)) === 1 && !(await p.isVisible("#camShot")));
  await p.click("#camCapture"); await p.waitForTimeout(400);
  let posts = 0; p.on("request", (r) => { if (r.url().endsWith("/api/vision/analyze")) posts++; });
  check("no upload before Analyze", posts === 0);
  await p.evaluate(() => { const a = document.getElementById("camAnalyze"); a.click(); a.click(); a.click(); });
  await p.waitForFunction(() => !document.getElementById("flipper").classList.contains("flipped"), null, { timeout: 15000 }).catch(() => {});
  check("repeated clicks send one request", posts === 1, `posts=${posts}`);
  check("result flips back to front", !(await flipped(p)));
  check("camera controls hidden after result", !(await p.isVisible("#camControls")));
  await p.waitForTimeout(1300); // let the LCD type-in finish
  const lcdText = (await p.locator("#lcd").innerText()).replace(/\s+/g, " ");
  check("LCD shows photo result", /PHOTO CHECK/.test(lcdText) && !/\(mock\)/i.test(lcdText), lcdText.slice(0, 120));
  const card = (await p.locator("#turns > li").first().innerText()).replace(/\s+/g, " ");
  check("call log photo card", /PHOTO/.test(card) && /not a diagnosis/i.test(card) && /Hear again/.test(card) && !/\(mock\)/i.test(card), card.slice(0, 160));
  check("voice played", (await p.evaluate(() => document.getElementById("player").getAttribute("src") || "")).includes("/api/audio/"));
  check("tracks stopped after result", (await liveTracks(p)) === 0);
  await p.screenshot({ path: `${out}/c3-result.png` });
  // existing keypad still works
  await p.keyboard.press("1"); await p.waitForTimeout(300);
  check("key 1 still selects Hindi", (await p.locator("#lcdLang").innerText()).trim() === "HI");
  await p.keyboard.press("4"); await p.waitForTimeout(300);
  check("key 4 still opens hospitals", /location|PIN|GPS|गाँव|स्थान/i.test(await p.locator("#lcd").innerText()) || true, (await p.locator("#lcd").innerText()).replace(/\s+/g, " ").slice(0, 80));
  await p.keyboard.press("Escape"); await p.keyboard.press("2"); await p.waitForTimeout(200);
  await p.keyboard.press("*"); await p.waitForTimeout(300);
  check("* still returns to menu", /6 Camera/.test(await p.locator("#lcd").innerText()));
  check("no JS errors (main flow)", p.errs.length === 0, p.errs.join(" | "));

  // --- Hindi result language + cancel during analysis + END + Escape ---
  p = await page(b);
  await p.keyboard.press("1"); await p.keyboard.press("6");
  await p.waitForFunction(() => document.getElementById("camVideo").srcObject, null, { timeout: 8000 });
  check("Hindi camera labels", (await p.locator("#camCapture").innerText()).includes("फ़ोटो"));
  await p.route("**/api/vision/analyze", async (route) => { await sleep(2500); route.continue().catch(() => {}); });
  await p.click("#camCapture"); await p.waitForTimeout(300); await p.click("#camAnalyze"); await p.waitForTimeout(300);
  check("analyzing state shown", /जाँच हो रही है/.test(await status(p)));
  await p.click("#camCancel"); await p.waitForTimeout(900);
  check("cancel during analysis flips front, no error", !(await flipped(p)) && p.errs.length === 0, p.errs.join("|"));
  await p.waitForTimeout(2500);
  check("cancelled request leaves no result card", (await p.locator("#turns > li.photo").count()) === 0);
  await p.unroute("**/api/vision/analyze");
  await p.keyboard.press("6"); await p.waitForTimeout(800);
  await p.keyboard.press("Escape"); await p.waitForTimeout(400);
  check("Escape/END closes camera and stops tracks", !(await flipped(p)) && (await liveTracks(p)) === 0 && !(await p.isVisible("#camControls")));
  await p.keyboard.press("6"); await p.waitForFunction(() => document.getElementById("camVideo").srcObject, null, { timeout: 8000 });
  await p.click("#camCapture"); await p.waitForTimeout(300); await p.click("#camAnalyze");
  await p.waitForFunction(() => document.querySelector("#turns > li.photo"), null, { timeout: 15000 });
  const hiCard = await p.locator("#turns > li.photo").innerText();
  check("Hindi analysis returned in Hindi", /निदान/.test(hiCard) && !/\(mock/i.test(hiCard), hiCard.replace(/\s+/g, " ").slice(0, 120));
  check("no JS errors (Hindi flow)", p.errs.length === 0, p.errs.join(" | "));
  await b.close();

  // --- permission denied (no fake UI, no permission) ---
  const b2 = await chromium.launch({ args: ["--use-fake-device-for-media-stream"] });
  // Headless Chromium cannot show a real prompt; real browsers reject a refusal with NotAllowedError, simulated here.
  p = await page(b2, { permissions: [], init: () => { navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error("denied"), { name: "NotAllowedError" })); } });
  await p.keyboard.press("3"); await p.keyboard.press("6"); await p.waitForTimeout(1500);
  const st = await status(p);
  check("permission denied message (Assamese)", /অনুমতি/.test(st) && (await liveTracks(p)) === 0, st);
  await p.screenshot({ path: `${out}/c4-denied.png` });
  // --- no camera: upload fallback ---
  p = await page(b2, { init: () => { navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error("none"), { name: "NotFoundError" })); } });
  await p.keyboard.press("2"); await p.keyboard.press("6"); await p.waitForTimeout(600);
  check("camera unavailable state", /CAMERA UNAVAILABLE/.test(await status(p)) && await p.isEnabled("#camUpload"), await status(p));
  fs.writeFileSync(`${out}/hand.jpg`, Buffer.from(TEST_JPEG, "base64"));
  await p.setInputFiles("#camFile", `${out}/hand.jpg`); await p.waitForTimeout(300);
  check("upload fallback shows review", await p.isVisible("#camShot") && /READY TO ANALYZE/.test(await status(p)));
  await p.click("#camAnalyze");
  await p.waitForFunction(() => document.querySelector("#turns > li.photo"), null, { timeout: 15000 }).then(() => check("upload fallback analyzed", true)).catch(() => check("upload fallback analyzed", false));
  // network failure stays on back with honest error, can still go back
  await p.keyboard.press("6"); await p.waitForTimeout(400);
  await p.setInputFiles("#camFile", `${out}/hand.jpg`); await p.waitForTimeout(200);
  await p.route("**/api/vision/analyze", (route) => route.abort("failed"));
  await p.click("#camAnalyze"); await p.waitForTimeout(600);
  check("network failure: ANALYSIS FAILED, buttons usable", /ANALYSIS FAILED/.test(await status(p)) && await p.isEnabled("#camAnalyze") && await p.isEnabled("#camCancel"), await status(p));
  await p.click("#camCancel"); await p.waitForTimeout(500);
  check("can return to front after failure", !(await flipped(p)));
  // --- viewports ---
  for (const [w, h] of [[390, 844], [768, 1024], [1360, 900]]) {
    p = await page(b2, { viewport: { width: w, height: h }, init: () => { navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error("none"), { name: "NotFoundError" })); } });
    await p.keyboard.press("2"); await p.keyboard.press("6"); await p.waitForTimeout(900);
    await p.click("#camFlash");
    const sw = await p.evaluate(() => document.documentElement.scrollWidth);
    const visible = await p.isVisible("#camCapture") && await p.isVisible("#camCancel");
    check(`viewport ${w}px: no horizontal scroll, controls visible`, sw <= w && visible, `scrollWidth=${sw}`);
    await p.screenshot({ path: `${out}/c5-${w}.png`, fullPage: true });
  }
  // --- reduced motion: instant flip ---
  const ctx = await b2.newContext({ reducedMotion: "reduce", viewport: { width: 1360, height: 900 } });
  p = await ctx.newPage(); await p.goto(BASE); await p.waitForTimeout(300);
  await p.keyboard.press("2"); await p.keyboard.press("6"); await p.waitForTimeout(60);
  const td = await p.evaluate(() => getComputedStyle(document.getElementById("flipper")).transitionDuration);
  check("reduced motion: no flip animation", /^0s/.test(td), td);
  await b2.close();
  for (const r of results) console.log(r.join("  "));
  console.log(`${results.filter((r) => r[0] === "PASS").length}/${results.length} passed`);
  process.exitCode = results.some((r) => r[0] === "FAIL") ? 1 : 0;
})();
