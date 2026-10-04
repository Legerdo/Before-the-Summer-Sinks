// HOT-Step YuE2 generator (adapted from the hot-step-yue2-music skill template).
// Usage: node.exe gen.mjs <trackDir> [<trackDir> ...]
// Each <trackDir> holds song.json {title, prompt, lyrics?, seed?, instrumental?}.
// Rules kept from the skill:
//  - one POST /api/generate per song, never re-submitted automatically; if job.json already exists
//    the existing job is polled again instead of submitting a new one
//  - waits while the shared queue is busy, never cancels other jobs
//  - the auth token lives only in memory
//  - backend/model mismatch => not submitted
import fs from "node:fs";
import path from "node:path";

const BASE = "http://127.0.0.1:3090";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const getJson = async (p, headers = {}) => {
  const r = await fetch(BASE + p, { headers, signal: AbortSignal.timeout(30000) });
  if (!r.ok) throw new Error(`GET ${p} -> ${r.status}`);
  return r.json();
};

function mkLog(dir) {
  return (m) => {
    const l = `[${new Date().toISOString()}] ${m}`;
    console.log(`${path.basename(dir)} ${l}`);
    fs.appendFileSync(path.join(dir, "gen.log"), l + "\n");
  };
}

async function waitIdle(log) {
  for (;;) {
    const q = await getJson("/api/generate/queue");
    if (!q.running && !q.pending) return;
    log("queue busy; waiting");
    await sleep(5000);
  }
}

async function runTrack(dir) {
  const log = mkLog(dir);
  const dest = path.join(dir, "source.wav");
  if (fs.existsSync(dest)) {
    log("source.wav exists; skipping");
    return "skipped";
  }
  const song = JSON.parse(fs.readFileSync(path.join(dir, "song.json"), "utf8"));
  if (!(await getJson("/api/health"))?.engine?.ready) throw new Error("engine not ready");
  const token = (await getJson("/api/auth/auto"))?.token;
  if (!token) throw new Error("no token");
  const H = { Authorization: `Bearer ${token}` };

  let jobId = null;
  const jobFile = path.join(dir, "job.json");
  if (fs.existsSync(jobFile)) {
    jobId = JSON.parse(fs.readFileSync(jobFile, "utf8")).jobId;
    log(`job.json present; resuming poll of jobId=${jobId} (no new submission)`);
  } else {
    await waitIdle(log);
    const be = await getJson("/api/backends");
    const m = await getJson("/api/backends/models?backend=yue2");
    log(`activeId=${be.activeId} lm=${m?.defaults?.lm} vae=${m?.defaults?.vae}`);
    if (be.activeId !== "yue2" || m?.defaults?.lm !== "q8_0" || m?.defaults?.vae !== "standard")
      throw new Error("backend mismatch; not submitted");
    const body = {
      backend: "yue2", title: song.title, prompt: song.prompt, lyrics: song.instrumental ? "" : song.lyrics,
      instrumental: !!song.instrumental, duration: 0, seed: song.seed ?? 20260930, randomSeed: false,
      batchSize: 1, yue2BatchSize: 1, yue2Variations: 1, yue2Cot: "full", yue2CfgScale: 1, yue2VaeVariant: "standard",
      yue2OdeSteps: 16, yue2NarSolver: "stock", yue2NarScheduler: "stock", yue2NarCacheRatio: 0,
      postProcessingEnabled: false, masteringEnabled: false, coverArtEnabled: false, parallelCoverArt: false,
      skipLrc: true, yue2AlignLyrics: false, autoTrimEnabled: false, streamMode: false,
    };
    fs.writeFileSync(path.join(dir, "request.json"), JSON.stringify(body, null, 2), "utf8");
    const r = await fetch(BASE + "/api/generate", {
      method: "POST", headers: { ...H, "Content-Type": "application/json; charset=utf-8" },
      body: Buffer.from(JSON.stringify(body), "utf8"), signal: AbortSignal.timeout(120000),
    });
    const txt = await r.text();
    if (!r.ok) throw new Error(`POST -> ${r.status}: ${txt.slice(0, 500)}`);
    jobId = JSON.parse(txt).jobId;
    if (!jobId) throw new Error(`no jobId: ${txt.slice(0, 300)}`);
    fs.writeFileSync(jobFile, JSON.stringify({ jobId }, null, 2));
    log(`submitted jobId=${jobId}`);
  }

  let st, last = "";
  const t0 = Date.now();
  for (;;) {
    await sleep(2000);
    try { st = await getJson(`/api/generate/status/${jobId}`, H); } catch (e) { log(`poll error: ${e.message}`); continue; }
    const s = `${st.status} ${st.progress ?? ""} ${st.stage ?? st.message ?? ""}`;
    if (s !== last) { log(s); last = s; }
    if (["succeeded", "failed", "cancelled"].includes(st.status)) break;
  }
  fs.writeFileSync(path.join(dir, "status-final.json"), JSON.stringify(st, null, 2));
  if (st.status !== "succeeded") {
    log(`job ${st.status}: ${JSON.stringify(st.error ?? st.message ?? "").slice(0, 400)}`);
    return `failed:${st.status}`;
  }
  const url = new URL(st.result.audioUrls[0], BASE).toString();
  const a = await fetch(url, { headers: H, signal: AbortSignal.timeout(120000) });
  if (!a.ok) throw new Error(`download ${a.status}`);
  const ext = path.extname(new URL(url).pathname).toLowerCase() || ".bin";
  const out = ext === ".wav" ? dest : path.join(dir, `source${ext}`);
  fs.writeFileSync(out, Buffer.from(await a.arrayBuffer()));
  log(`saved ${out} after ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  return "ok";
}

const dirs = process.argv.slice(2).map((d) => path.resolve(d));
const summary = [];
for (const d of dirs) {
  try {
    summary.push([path.basename(d), await runTrack(d)]);
  } catch (e) {
    mkLog(d)(`ERROR: ${e.message}`);
    summary.push([path.basename(d), `error:${e.message}`]);
  }
}
console.log("SUMMARY " + JSON.stringify(summary));
