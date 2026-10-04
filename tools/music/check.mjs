// Read-only status check of the local HOT-Step server (health, queue, backend, yue2 model defaults).
// The auth token is only used to confirm it can be obtained; it is never printed or stored.
const BASE = "http://127.0.0.1:3090";
const getJson = async (p, headers = {}) => {
  const r = await fetch(BASE + p, { headers, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error(`GET ${p} -> ${r.status}`);
  return r.json();
};
try {
  const h = await getJson("/api/health");
  console.log("health.engine.ready =", h?.engine?.ready, "| keys:", Object.keys(h || {}).join(","));
  const q = await getJson("/api/generate/queue");
  console.log("queue:", JSON.stringify({ running: q.running ?? null, pending: q.pending ?? null }).slice(0, 300));
  const be = await getJson("/api/backends");
  console.log("backends.activeId =", be.activeId);
  const m = await getJson("/api/backends/models?backend=yue2");
  console.log("yue2 defaults =", JSON.stringify(m?.defaults));
  const t = await getJson("/api/auth/auto");
  console.log("token available =", Boolean(t?.token));
} catch (e) {
  console.log("ERROR:", e.message);
  process.exitCode = 1;
}
