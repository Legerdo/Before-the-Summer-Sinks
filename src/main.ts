import "./styles.css";
import { Game } from "./game";
import type { Assets, Story } from "./engine/types";

const BASE = "./";

async function json<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return (await r.json()) as T;
}

async function boot() {
  const host = document.getElementById("app")!;
  const [assets, story, lipsync] = await Promise.all([
    json<Assets>("data/assets.json"),
    json<Story>("data/story.json"),
    json<Record<string, string>>("data/lipsync.json").catch(() => ({})),
  ]);
  const game = new Game(host, assets, story, BASE, lipsync);
  const params = new URLSearchParams(location.search);

  // Automation / QA hooks (used by the Playwright route checker; harmless for players).
  window.__vn = {
    game,
    story,
    assets,
    errors: game.errors,
    /** Run the story headlessly from a label with scripted choices; resolves at an ending. */
    async run(opts: { label?: string; choices?: number[]; maxLines?: number }) {
      game.testMode = true;
      game.mode = "play";
      game.stage.fast = true;
      if (!game.vm.visited) game.vm.visited = new Set();
      game.testChoices = [...(opts.choices ?? [])];
      const t0 = performance.now();
      const start = game.lineCount;
      game.lastEnding = null;
      const p = game.vm.start(opts.label ?? "start");
      await p;
      return { lines: game.lineCount - start, ms: performance.now() - t0, vars: game.vm.vars, errors: [...game.errors], pc: game.vm.pc, ending: game.lastEnding };
    },
    snapshot: () => game.vm.lastSnap,
    coverage: () => {
      const v = game.vm.visited ?? new Set<number>();
      const unvisited: string[] = [];
      story.code.forEach((_c, i) => { if (!v.has(i)) unvisited.push(story.srcmap[i]); });
      return { total: story.code.length, visited: v.size, unvisited };
    },
    endings: () => game.store.global.endings,
    /**
     * Fast-forward (instant, silent) from *start with scripted choices until the first dialogue line at
     * or after `loc` ("03_ch3.vn:120"), then continue in normal interactive mode from there.
     */
    seek(opts: { loc: string; choices?: number[] }) {
      const [file, lineStr] = opts.loc.split(":");
      const want = Number(lineStr);
      const target = story.srcmap.findIndex((l, i) => {
        const [f, n] = l.split(":");
        return f === file && Number(n) >= want && story.code[i].op === "say";
      });
      if (target < 0) throw new Error("no line at " + opts.loc);
      game.testMode = true;
      game.stage.fast = true;
      game.mode = "play";
      game.testChoices = [...(opts.choices ?? [])];
      game.vm.onStep = (pc) => {
        if (pc === target) {
          game.testMode = false;
          game.stage.fast = false;
          game.vm.onStep = null;
          window.dispatchEvent(new CustomEvent("vn-seek-done"));
        }
      };
      void game.vm.start("start");
      return target;
    },
    /** Play one voice line on an on-stage sprite and sample mouth/eye layers every frame. */
    async lipsyncProbe(voice: string, who = "yunseul", expr = "neutral", pose?: string) {
      await game.audio.unlock();
      game.mode = "play";
      game.stage.clearAll();
      await game.stage.setBg("village_day", "none", 0);
      await game.stage.show(who, pose, expr, 0.5, 0);
      const el = document.querySelector(`.sprite[data-char="${who}"]`)!;
      const samples: { t: number; mouth: number; eyes: number; wall: number }[] = [];
      const h = await game.playLineVoice({ op: "say", id: "probe", who, text: "", voice });
      if (!h) return { error: "no voice" };
      const t0 = performance.now();
      await new Promise<void>((resolve) => {
        const step = () => {
          const m1 = el.querySelector<HTMLElement>(".sp-mouth1");
          const m2 = el.querySelector<HTMLElement>(".sp-mouth2");
          const ey = el.querySelector<HTMLElement>(".sp-eyes");
          const mouth = m2 && m2.style.opacity === "1" ? 2 : m1 && m1.style.opacity === "1" ? 1 : 0;
          samples.push({ t: game.audio.voiceTime(h), mouth, eyes: ey && ey.style.opacity === "1" ? 1 : 0, wall: performance.now() - t0 });
          if (h.ended && performance.now() - t0 > (h.duration + 0.5) * 1000) resolve();
          else requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      });
      const env = game.env(voice);
      return { dur: h.duration, samples, env: env ? Array.from(env) : [] };
    },
    /** Fetch + decode every audio file and decode every image; returns failures. */
    async verifyAssets() {
      await game.audio.unlock();
      const fails: string[] = [];
      const audio = [
        ...Object.values(assets.bgm).map((b) => b.src), ...Object.values(assets.amb).map((b) => b.src),
        ...Object.values(assets.se).map((b) => b.src), ...Object.values(assets.voice).map((b) => b.src),
      ];
      const ctx = game.audio.ctx!;
      let decoded = 0;
      const durMismatch: string[] = [];
      for (let i = 0; i < audio.length; i += 12) {
        await Promise.all(audio.slice(i, i + 12).map(async (src) => {
          try {
            const r = await fetch(BASE + src);
            if (!r.ok) throw new Error(String(r.status));
            const buf = await ctx.decodeAudioData(await r.arrayBuffer());
            if (buf.duration < 0.05) throw new Error("empty");
            decoded++;
            const v = Object.values(assets.voice).find((x) => x.src === src);
            if (v && Math.abs(v.dur - buf.duration) > 0.15) durMismatch.push(`${src} ${v.dur} vs ${buf.duration.toFixed(3)}`);
          } catch (e) {
            fails.push(`audio ${src}: ${(e as Error).message}`);
          }
        }));
      }
      const imgs = [
        ...Object.values(assets.bg).map((b) => b.src), ...Object.values(assets.cg).flatMap((b) => [b.src, b.thumb ?? b.src]),
        ...Object.values(assets.chars).flatMap((c) => [...Object.values(c.bodies), ...Object.values(c.faces).flatMap((f) => [f.face.src, ...(f.eyes ? [f.eyes.src] : []), ...f.mouth.map((m) => m.src)])]),
      ];
      let imgOk = 0;
      for (const src of imgs) {
        const im = new Image();
        im.src = BASE + src;
        try {
          await im.decode();
          imgOk++;
        } catch {
          fails.push(`image ${src}`);
        }
      }
      return { audio: audio.length, decoded, images: imgs.length, imgOk, fails, durMismatch };
    },
  };

  if (params.has("test") || params.has("qa")) {
    await game.audio.unlock();
    if (params.has("test")) document.body.classList.add("test");
    return;
  }
  await game.screens.splash();
  if (params.has("label")) {
    game.mode = "play";
    await game.vm.start(params.get("label")!);
    return;
  }
  game.screens.title();
}

boot().catch((e) => {
  console.error(e);
  document.body.innerHTML = `<pre style="color:#fff;padding:2em">부팅 실패: ${(e as Error).message}</pre>`;
});
