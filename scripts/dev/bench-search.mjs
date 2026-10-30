/* NIL TV web - search overlay benchmark and regression check.
   Drives a headless Edge/Chrome over the DevTools protocol against the local
   dev server, on a phone profile, and measures the search overlay in
   assets/js/app.js. docs/search-review.md has the numbers this reproduces.

     python scripts/dev/serve.py                 (separate terminal, with fixtures)
     node scripts/dev/bench-search.mjs load      open -> first results, API requests, KB
     node scripts/dev/bench-search.mjs typing    main-thread cost and result delay while typing
     node scripts/dev/bench-search.mjs check     stale-result / failed-load regressions (exit 1 on failure)

   Options: --runs N, --profile mobile|mobile-api|desktop (load), --ms N per
   keystroke (typing), --url <page> (default http://localhost:8787/channels/).
   Browser: BROWSER_PATH, else the usual Edge/Chrome install locations.
   Node 22+ (global WebSocket), or Node 20 with --experimental-websocket. No deps. */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const PROFILES = {
  // Lighthouse mobile defaults: 150 ms RTT, 1.6 Mbps down, 750 Kbps up, 4x CPU
  mobile: { latency: 150, down: 200000, up: 93750, cpu: 4 },
  // same, with the RTT raised to the dev API's measured ~1.2 s per request
  "mobile-api": { latency: 1200, down: 200000, up: 93750, cpu: 4 },
  desktop: { latency: 0, down: -1, up: -1, cpu: 1 },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
function die(msg) { console.error("bench-search: " + msg); process.exit(2); }

function parseArgs(argv) {
  const opts = { cmd: argv[0], runs: null, profile: "mobile", ms: 200, url: "http://localhost:8787/channels/" };
  for (let i = 1; i < argv.length; i += 2) {
    const k = argv[i].replace(/^--/, ""), v = argv[i + 1];
    if (!(k in opts) || v === undefined) die("unknown or incomplete option " + argv[i]);
    opts[k] = k === "runs" || k === "ms" ? Number(v) : v;
  }
  return opts;
}

/* ── browser ─────────────────────────────────────────────── */

function findBrowser() {
  return [
    process.env.BROWSER_PATH,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/microsoft-edge",
  ].find((p) => p && existsSync(p));
}

async function launchBrowser() {
  const exe = findBrowser();
  if (!exe) die("no Edge or Chrome found; set BROWSER_PATH");
  const dir = await mkdtemp(path.join(os.tmpdir(), "niltv-bench-"));
  // A fresh profile otherwise spends its first minute on background work
  // (component updates, safe-browsing lists...) that competes with the
  // throttled page for CPU. Same switches Puppeteer launches with.
  spawn(exe, ["--headless=new", "--remote-debugging-port=0", "--user-data-dir=" + dir,
    "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
    "--disable-component-update", "--disable-sync", "--disable-extensions", "--disable-default-apps",
    "--disable-features=Translate,OptimizationHints,MediaRouter", "--metrics-recording-only",
    "about:blank"], { stdio: "ignore" });
  // the browser writes its chosen port to DevToolsActivePort once it's listening
  let port = "";
  for (let i = 0; i < 150 && !port; i++) {
    await sleep(100);
    port = await readFile(path.join(dir, "DevToolsActivePort"), "utf8").then((s) => s.split("\n")[0].trim(), () => "");
  }
  // On Windows the spawned process is only a launcher that hands off and exits
  // within milliseconds, so `proc` can't be used to track or kill the browser.
  // Every process of this browser has the throwaway profile dir on its command
  // line; that's what the fallback kill matches.
  const killByProfile = () => new Promise((resolve) => {
    const k = process.platform === "win32"
      ? spawn("powershell", ["-NoProfile", "-Command",
        `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*${path.basename(dir)}*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }`],
      { stdio: "ignore" })
      : spawn("pkill", ["-9", "-f", path.basename(dir)], { stdio: "ignore" });
    k.on("exit", resolve);
    k.on("error", resolve);
  });
  const alive = () => fetch(`http://127.0.0.1:${port}/json/version`).then(() => true, () => false);
  if (!port) { await killByProfile(); die("browser didn't start: " + exe); }
  return {
    port,
    close: async () => {
      try {
        const { webSocketDebuggerUrl } = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
        const ws = new WebSocket(webSocketDebuggerUrl);
        await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
        ws.send(JSON.stringify({ id: 1, method: "Browser.close" }));
      } catch (e) { /* fall through to the kill below */ }
      for (let i = 0; i < 50 && await alive(); i++) await sleep(100);
      if (await alive()) await killByProfile();
      await rm(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 }).catch(() => {});
    },
  };
}

// One page target with a minimal CDP client, sized like a phone.
async function openPage(port) {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = {}, listeners = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending[msg.id]) { pending[msg.id](msg); delete pending[msg.id]; }
    else if (msg.method) listeners.forEach((f) => f(msg));
  };
  const send = (method, params = {}) => new Promise((resolve) => {
    const i = ++id; pending[i] = resolve; ws.send(JSON.stringify({ id: i, method, params }));
  });
  const page = {
    send,
    on: (f) => listeners.push(f),
    evaluate: async (expression) => {
      const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      const ex = r.result && r.result.exceptionDetails;
      if (ex) throw new Error((ex.exception && ex.exception.description) || ex.text);
      return r.result.result.value;
    },
    navigate: async (url, reload) => {
      const loaded = new Promise((resolve) => {
        const f = (m) => { if (m.method === "Page.loadEventFired") { listeners.splice(listeners.indexOf(f), 1); resolve(); } };
        listeners.push(f);
      });
      await send(reload ? "Page.reload" : "Page.navigate", reload ? {} : { url });
      await loaded;
      await page.evaluate("sessionStorage.clear()"); // api() caches GETs there for 60s
    },
    throttle: async (p, cpu = p.cpu) => {
      await send("Network.emulateNetworkConditions", { offline: false, latency: p.latency, downloadThroughput: p.down, uploadThroughput: p.up });
      await send("Emulation.setCPUThrottlingRate", { rate: cpu });
    },
    metric: async (name) => (await send("Performance.getMetrics")).result.metrics.find((m) => m.name === name).value,
    close: async () => { ws.close(); await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`); },
  };
  for (const m of ["Page.enable", "Network.enable", "Performance.enable"]) await send(m);
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  return page;
}

// In-page helpers shared by every scenario.
const HELPERS = `
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const inp = () => document.getElementById("search-input");
  const type = (q) => { inp().value = q; inp().dispatchEvent(new Event("input")); };
  const state = () => {
    const rows = [...document.querySelectorAll("#search-results .search-row")].map((n) => n.textContent);
    const hints = [...document.querySelectorAll("#search-results .search-hint")].map((n) => n.textContent);
    return { rows: rows.length, unique: new Set(rows).size, hints };
  };
  const until = async (ok, ms) => { const t = performance.now(); while (!ok() && performance.now() - t < ms) await wait(10); };`;

/* ── scenarios ───────────────────────────────────────────── */

// Cold open: index build over the network until the first result rows show.
async function benchLoad(port, opts) {
  const profile = PROFILES[opts.profile] || die("unknown profile " + opts.profile);
  const runs = [];
  for (let r = 0; r < (opts.runs || 3); r++) {
    const page = await openPage(port);
    await page.send("Network.setCacheDisabled", { cacheDisabled: true }); // a first visit
    await page.navigate(opts.url);
    await page.throttle(profile); // after the page itself loads: only search is being timed
    runs.push(await page.evaluate(`(async () => { ${HELPERS}
      const before = performance.getEntriesByType("resource").length;
      const t0 = performance.now();
      NILTV.openSearch(); type("tv");
      await until(() => state().rows, 60000);
      const firstResultsMs = Math.round(performance.now() - t0);
      const api = performance.getEntriesByType("resource").slice(before).filter((e) => e.name.includes("/v1/"));
      return { firstResultsMs, requests: api.length, kb: Math.round(api.reduce((s, e) => s + e.encodedBodySize, 0) / 1024) };
    })()`));
    await page.close();
    console.log(`  run ${r + 1}: ${JSON.stringify(runs[r])}`);
  }
  console.log(`load (${opts.profile}): median ${median(runs.map((x) => x.firstResultsMs))} ms to first results, ` +
    `${runs[0].requests} API requests, ${runs[0].kb} KB`);
}

// Warm index, then type "nil tv" one key every --ms milliseconds on a 4x CPU.
// Typing is CPU-bound, so only the CPU is throttled.
async function benchTyping(port, opts) {
  const page = await openPage(port);
  await page.navigate(opts.url);
  // build the index and get every result thumbnail loaded and cached first,
  // so the runs time the search code rather than image downloads and decodes
  await page.evaluate(`(async () => { ${HELPERS}
    NILTV.openSearch(); type("nil tv"); await until(() => state().rows, 60000);
    const imgs = () => [...document.querySelectorAll("#search-results img")];
    await until(() => imgs().every((i) => i.complete), 30000); await wait(500); })()`);
  await page.throttle(PROFILES.desktop, PROFILES.mobile.cpu);
  const runs = [];
  for (let r = 0; r < (opts.runs || 7); r++) {
    await page.evaluate(`(async () => { ${HELPERS} type(""); await wait(600); })()`);
    const t0 = await page.metric("TaskDuration");
    const run = await page.evaluate(`(async () => { ${HELPERS}
      const out = document.getElementById("search-results");
      let rebuilds = 0, lastChange = 0, lastKey = 0;
      const mo = new MutationObserver((recs) => {
        lastChange = performance.now();
        if (recs.some((rec) => [...rec.addedNodes].some((n) => n.classList && n.classList.contains("search-row")))) rebuilds++;
      });
      mo.observe(out, { childList: true });
      const q = "nil tv";
      for (let k = 1; k <= q.length; k++) { type(q.slice(0, k)); lastKey = performance.now(); await wait(${opts.ms}); }
      await wait(800);
      mo.disconnect();
      return { rebuilds, resultDelayMs: Math.max(0, Math.round(lastChange - lastKey)) };
    })()`);
    run.mainThreadMs = Math.round((await page.metric("TaskDuration") - t0) * 1000);
    runs.push(run);
    console.log(`  run ${r + 1}: ${JSON.stringify(run)}`);
  }
  await page.close();
  console.log(`typing (${opts.ms} ms/key): median ${median(runs.map((x) => x.mainThreadMs))} ms main thread, ` +
    `${median(runs.map((x) => x.rebuilds))} list rebuilds, results ${median(runs.map((x) => x.resultDelayMs))} ms after the last key`);
}

// Regression check for the stale-result and failed-load fixes.
async function check(port, opts) {
  const page = await openPage(port);
  const exceptions = [];
  let failNext = 0;
  page.on((msg) => {
    if (msg.method === "Runtime.exceptionThrown") {
      const d = msg.params.exceptionDetails;
      exceptions.push((d.exception && d.exception.description) || d.text);
    }
    if (msg.method === "Fetch.requestPaused") {
      const requestId = msg.params.requestId;
      if (failNext > 0) { failNext--; page.send("Fetch.failRequest", { requestId, errorReason: "InternetDisconnected" }); }
      // hold the index load open so keystrokes land while it's in flight
      else setTimeout(() => page.send("Fetch.continueRequest", { requestId }), 1500);
    }
  });
  await page.send("Runtime.enable"); // for exceptionThrown
  await page.send("Network.setCacheDisabled", { cacheDisabled: true }); // every load must hit Fetch
  await page.send("Fetch.enable", { patterns: [{ urlPattern: "*/v1/channels*" }] });

  const results = [];
  const expect = (name, ok, got) => results.push({ name, ok, got });
  await page.navigate(opts.url);

  failNext = 1;
  let s = await page.evaluate(`(async () => { ${HELPERS} NILTV.openSearch(); type("nil"); await wait(800); return state(); })()`);
  expect("failed index load shows a message", s.rows === 0 && s.hints.length === 1, s);
  s = await page.evaluate(`(async () => { ${HELPERS} type("nil "); await until(() => state().rows, 5000); return state(); })()`);
  expect("next keystroke retries the load", s.rows > 0, s);
  expect("no uncaught errors", exceptions.length === 0, exceptions);

  await page.navigate(opts.url, true);
  s = await page.evaluate(`(async () => { ${HELPERS}
    NILTV.openSearch(); type("ni"); await wait(60); type("nil"); await wait(60); type("nil ");
    await until(() => state().rows, 5000); await wait(500); return state(); })()`);
  expect("typing during load renders one result set", s.rows > 0 && s.rows === s.unique, s);

  await page.navigate(opts.url, true);
  s = await page.evaluate(`(async () => { ${HELPERS}
    NILTV.openSearch(); type("nil"); await wait(60); type("n"); await wait(2500); return state(); })()`);
  expect("deleting below 2 chars during load leaves only the hint", s.rows === 0 && s.hints.length === 1, s);
  await page.close();

  for (const r of results) console.log(`  ${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.ok ? "" : "  " + JSON.stringify(r.got)}`);
  const failed = results.filter((r) => !r.ok).length;
  console.log(failed ? `check: ${failed} failed` : "check: all passed");
  return failed ? 1 : 0;
}

/* ── main ────────────────────────────────────────────────── */

const opts = parseArgs(process.argv.slice(2));
const commands = { load: benchLoad, typing: benchTyping, check };
if (!commands[opts.cmd]) die("usage: node scripts/dev/bench-search.mjs load|typing|check [--runs N] [--profile P] [--ms N] [--url U]");
if (typeof WebSocket === "undefined") die("needs Node 22+, or Node 20 with --experimental-websocket");

const origin = new URL(opts.url).origin;
const channels = await fetch(origin + "/v1/channels").then((r) => r.json(), () => null);
if (!channels) die(`nothing answering at ${origin}; start python scripts/dev/serve.py first`);
if (!(channels.channels || []).length) die("the API returned no channels; run python scripts/dev/capture-fixtures.py");

const browser = await launchBrowser();
let code = 0;
try { code = (await commands[opts.cmd](browser.port, opts)) || 0; }
finally { await browser.close(); }
process.exit(code);
