// Web Audio engine: buses, looping BGM with crossfades, ambience beds, sound effects,
// voice playback with character/scene FX chains (radio, tape, phone, echo, PA, room)
// and precise playback timing for lip sync.

import type { Assets } from "./types";

export type Bus = "bgm" | "amb" | "se" | "voice" | "sys";

interface Playing {
  id: string;
  src: AudioBufferSourceNode;
  gain: GainNode;
  vol: number;
}

export interface VoiceHandle {
  id: string;
  startAt: number; // context time the first sample is scheduled
  duration: number;
  ended: boolean;
  done: Promise<void>;
  stop(): void;
}

interface FxChain {
  input: AudioNode;
  output: AudioNode;
  extras: AudioScheduledSourceNode[];
}

const perceptual = (v: number) => Math.max(0, Math.min(1, v)) ** 2;

export class AudioEngine {
  ctx: AudioContext | null = null;
  private master!: GainNode;
  private buses = {} as Record<Bus, GainNode>;
  private duck!: GainNode;
  private buffers = new Map<string, Promise<AudioBuffer | null>>();
  private bgm: Playing | null = null;
  private amb = new Map<string, Playing>();
  private sfxLoop: Playing | null = null;
  private voice: { handle: VoiceHandle; src: AudioBufferSourceNode; chain: FxChain } | null = null;
  private noise: AudioBuffer | null = null;
  private irRoom: AudioBuffer | null = null;
  private vols: Record<Bus | "master", number> = { master: 0.8, bgm: 0.55, amb: 0.6, se: 0.7, voice: 0.9, sys: 0.5 };
  duckAmount = 0.62;
  onError: (msg: string) => void = () => {};

  constructor(private assets: Assets, private base: string) {}

  get ready() {
    return this.ctx !== null;
  }

  /** Must be called from a user gesture in browsers. */
  async unlock() {
    if (!this.ctx) {
      const ctx = new AudioContext({ latencyHint: "interactive" });
      this.ctx = ctx;
      this.master = ctx.createGain();
      this.master.connect(ctx.destination);
      this.duck = ctx.createGain();
      this.duck.connect(this.master);
      for (const b of ["bgm", "amb", "se", "voice", "sys"] as Bus[]) {
        const g = ctx.createGain();
        g.connect(b === "bgm" ? this.duck : this.master);
        this.buses[b] = g;
      }
      this.applyVolumes();
      this.noise = this.makeNoise(4);
      this.irRoom = this.makeIR(0.7, 2.4);
    }
    if (this.ctx.state !== "running") await this.ctx.resume().catch(() => {});
  }

  setVolumes(v: Partial<Record<Bus | "master", number>>) {
    Object.assign(this.vols, v);
    this.applyVolumes();
  }

  private applyVolumes() {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.master.gain.setTargetAtTime(perceptual(this.vols.master), t, 0.03);
    for (const b of Object.keys(this.buses) as Bus[]) this.buses[b].gain.setTargetAtTime(perceptual(this.vols[b]), t, 0.03);
  }

  private url(src: string) {
    return this.base + src;
  }

  load(src: string): Promise<AudioBuffer | null> {
    let p = this.buffers.get(src);
    if (!p) {
      p = (async () => {
        try {
          const r = await fetch(this.url(src));
          if (!r.ok) throw new Error(`${r.status}`);
          const data = await r.arrayBuffer();
          const ctx = this.ctx ?? new OfflineAudioContext(2, 1, 44100);
          return await ctx.decodeAudioData(data);
        } catch (e) {
          this.onError(`audio load failed: ${src} (${(e as Error).message})`);
          return null;
        }
      })();
      this.buffers.set(src, p);
    }
    return p;
  }

  preload(srcs: string[]) {
    for (const s of srcs) void this.load(s);
  }

  // ------------------------------------------------------------------ BGM
  get bgmId() {
    return this.bgm?.id ?? null;
  }

  async playBgm(id: string | null, fade = 1.5, vol = 1) {
    if (!this.ctx) return;
    if (id === null || id === "stop" || id === "off") {
      this.stopBgm(fade);
      return;
    }
    if (this.bgm && this.bgm.id === id) {
      this.bgm.vol = vol;
      this.bgm.gain.gain.setTargetAtTime(vol, this.ctx.currentTime, Math.max(0.05, fade / 3));
      return;
    }
    const meta = this.assets.bgm[id];
    if (!meta) {
      this.onError(`unknown bgm ${id}`);
      return;
    }
    const want = id;
    this.stopBgm(fade);
    const buf = await this.load(meta.src);
    if (!buf || !this.ctx) return;
    if (this.bgm && this.bgm.id !== want) this.stopBgm(fade);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    if (meta.loop) {
      src.loop = true;
      src.loopStart = meta.loopStart ?? 0;
      src.loopEnd = meta.loopEnd ?? buf.duration;
    }
    const gain = this.ctx.createGain();
    const t = this.ctx.currentTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(vol, t + Math.max(0.05, fade));
    src.connect(gain).connect(this.buses.bgm);
    src.start(t + 0.02);
    this.bgm = { id, src, gain, vol };
    this.heard.add(id);
    this.onBgm(id);
  }

  heard = new Set<string>();
  onBgm: (id: string) => void = () => {};

  stopBgm(fade = 1.5) {
    if (!this.ctx || !this.bgm) return;
    const { src, gain } = this.bgm;
    const t = this.ctx.currentTime;
    gain.gain.cancelScheduledValues(t);
    gain.gain.setValueAtTime(gain.gain.value, t);
    gain.gain.linearRampToValueAtTime(0, t + Math.max(0.03, fade));
    src.stop(t + Math.max(0.03, fade) + 0.05);
    this.bgm = null;
  }

  // ------------------------------------------------------------------ ambience
  async setAmb(ids: string[], fade = 2) {
    if (!this.ctx) return;
    const want = new Set(ids.filter((i) => i && i !== "stop" && i !== "off"));
    for (const [id, p] of this.amb) {
      if (!want.has(id)) {
        this.fadeStop(p, fade);
        this.amb.delete(id);
      }
    }
    for (const id of want) {
      if (this.amb.has(id)) continue;
      const meta = this.assets.amb[id];
      if (!meta) {
        this.onError(`unknown amb ${id}`);
        continue;
      }
      const p = await this.startLoop(id, meta.src, meta.vol ?? 1, fade, this.buses.amb);
      if (p) {
        if (!want.has(id) || this.amb.has(id)) this.fadeStop(p, 0.1);
        else this.amb.set(id, p);
      }
    }
  }

  async setSfxLoop(id: string | null, fade = 0.6) {
    if (!this.ctx) return;
    if (this.sfxLoop && this.sfxLoop.id !== id) {
      this.fadeStop(this.sfxLoop, fade);
      this.sfxLoop = null;
    }
    if (!id || id === "stop" || id === "off" || this.sfxLoop) return;
    const meta = this.assets.se[id] ?? this.assets.amb[id];
    if (!meta) {
      this.onError(`unknown se ${id}`);
      return;
    }
    this.sfxLoop = await this.startLoop(id, meta.src, meta.vol ?? 1, fade, this.buses.se);
  }

  private async startLoop(id: string, srcPath: string, vol: number, fade: number, bus: GainNode): Promise<Playing | null> {
    const buf = await this.load(srcPath);
    if (!buf || !this.ctx) return null;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    const gain = this.ctx.createGain();
    const t = this.ctx.currentTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(vol, t + Math.max(0.05, fade));
    src.connect(gain).connect(bus);
    // random offset so repeated scenes don't start identically
    src.start(t + 0.01, Math.random() * Math.max(0, buf.duration - 1));
    return { id, src, gain, vol };
  }

  private fadeStop(p: Playing, fade: number) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    p.gain.gain.cancelScheduledValues(t);
    p.gain.gain.setValueAtTime(p.gain.gain.value, t);
    p.gain.gain.linearRampToValueAtTime(0, t + Math.max(0.03, fade));
    p.src.stop(t + Math.max(0.03, fade) + 0.05);
  }

  stopAll(fade = 0.5) {
    this.stopBgm(fade);
    void this.setAmb([], fade);
    void this.setSfxLoop(null, fade);
    this.stopVoice();
  }

  // ------------------------------------------------------------------ one-shots
  async se(id: string, vol = 1, delay = 0, bus: Bus = "se") {
    if (!this.ctx) return;
    const meta = this.assets.se[id];
    if (!meta) {
      this.onError(`unknown se ${id}`);
      return;
    }
    const buf = await this.load(meta.src);
    if (!buf || !this.ctx) return;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const g = this.ctx.createGain();
    g.gain.value = vol * (meta.vol ?? 1);
    src.connect(g).connect(this.buses[bus]);
    src.start(this.ctx.currentTime + delay);
  }

  ui(id: string, vol = 1) {
    void this.se(id, vol, 0, "sys");
  }

  // ------------------------------------------------------------------ voice
  get speaking(): VoiceHandle | null {
    return this.voice && !this.voice.handle.ended ? this.voice.handle : null;
  }

  async playVoice(id: string, fx = "none", vol = 1): Promise<VoiceHandle | null> {
    if (!this.ctx) return null;
    this.stopVoice();
    const meta = this.assets.voice[id];
    if (!meta) {
      this.onError(`missing voice ${id}`);
      return null;
    }
    const buf = await this.load(meta.src);
    if (!buf || !this.ctx) return null;
    this.stopVoice();
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const chain = this.buildFx(fx);
    const g = ctx.createGain();
    g.gain.value = vol;
    src.connect(g).connect(chain.input);
    chain.output.connect(this.buses.voice);
    const startAt = ctx.currentTime + 0.03;
    let resolve!: () => void;
    const done = new Promise<void>((r) => (resolve = r));
    const handle: VoiceHandle = {
      id,
      startAt,
      duration: buf.duration,
      ended: false,
      done,
      stop: () => {
        if (handle.ended) return;
        try {
          src.stop();
        } catch {
          /* already stopped */
        }
      },
    };
    src.onended = () => {
      handle.ended = true;
      for (const x of chain.extras) {
        try {
          x.stop();
        } catch {
          /* noop */
        }
      }
      setTimeout(() => {
        try {
          chain.output.disconnect();
        } catch {
          /* noop */
        }
      }, 1500);
      this.unduck();
      resolve();
    };
    src.start(startAt);
    for (const x of chain.extras) x.start(startAt);
    this.voice = { handle, src, chain };
    this.duckBgm();
    return handle;
  }

  stopVoice() {
    if (this.voice) {
      this.voice.handle.stop();
      this.voice = null;
    }
  }

  /** Seconds of the current voice that have actually reached the speakers. */
  voiceTime(h: VoiceHandle): number {
    if (!this.ctx) return 0;
    const lat = (this.ctx as AudioContext & { outputLatency?: number }).outputLatency ?? 0;
    return this.ctx.currentTime - h.startAt - (lat || this.ctx.baseLatency || 0);
  }

  private duckBgm() {
    if (!this.ctx) return;
    this.duck.gain.setTargetAtTime(this.duckAmount, this.ctx.currentTime, 0.12);
  }

  private unduck() {
    if (!this.ctx) return;
    this.duck.gain.setTargetAtTime(1, this.ctx.currentTime + 0.25, 0.4);
  }

  // ------------------------------------------------------------------ FX
  private makeNoise(seconds: number): AudioBuffer {
    const ctx = this.ctx!;
    const n = Math.floor(ctx.sampleRate * seconds);
    const b = ctx.createBuffer(1, n, ctx.sampleRate);
    const d = b.getChannelData(0);
    // pinkish noise (Paul Kellet)
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < n; i++) {
      const w = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + w * 0.0555179;
      b1 = 0.99332 * b1 + w * 0.0750759;
      b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856;
      b4 = 0.55 * b4 + w * 0.5329522;
      b5 = -0.7616 * b5 - w * 0.016898;
      d[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11;
      b6 = w * 0.115926;
    }
    return b;
  }

  private makeIR(seconds: number, decay: number): AudioBuffer {
    const ctx = this.ctx!;
    const n = Math.floor(ctx.sampleRate * seconds);
    const b = ctx.createBuffer(2, n, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c);
      for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n) ** decay * 0.6;
    }
    return b;
  }

  private shaper(k: number): WaveShaperNode {
    const ws = this.ctx!.createWaveShaper();
    const n = 1024;
    const curve = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;
      curve[i] = Math.tanh(k * x) / Math.tanh(k);
    }
    ws.curve = curve;
    ws.oversample = "2x";
    return ws;
  }

  private biquad(type: BiquadFilterType, f: number, q = 0.707, gain = 0): BiquadFilterNode {
    const b = this.ctx!.createBiquadFilter();
    b.type = type;
    b.frequency.value = f;
    b.Q.value = q;
    b.gain.value = gain;
    return b;
  }

  private noiseBed(level: number, hp: number, lp: number, out: AudioNode): AudioBufferSourceNode {
    const ctx = this.ctx!;
    const s = ctx.createBufferSource();
    s.buffer = this.noise;
    s.loop = true;
    const g = ctx.createGain();
    g.gain.value = level;
    s.connect(this.biquad("highpass", hp)).connect(this.biquad("lowpass", lp)).connect(g).connect(out);
    return s;
  }

  buildFx(kind: string): FxChain {
    const ctx = this.ctx!;
    const input = ctx.createGain();
    const output = ctx.createGain();
    const extras: AudioScheduledSourceNode[] = [];
    const chain = (...nodes: AudioNode[]) => {
      let prev: AudioNode = input;
      for (const n of nodes) {
        prev.connect(n);
        prev = n;
      }
      prev.connect(output);
    };
    switch (kind) {
      case "radio": {
        const post = ctx.createGain();
        post.gain.value = 0.95;
        chain(this.biquad("highpass", 290), this.biquad("lowpass", 3900), this.biquad("peaking", 1700, 0.9, 4), this.shaper(1.8), post);
        extras.push(this.noiseBed(0.018, 900, 6000, output));
        break;
      }
      case "tape": {
        const delay = ctx.createDelay(0.05);
        delay.delayTime.value = 0.006;
        const wow = ctx.createOscillator();
        wow.frequency.value = 0.55;
        const wowG = ctx.createGain();
        wowG.gain.value = 0.0012;
        wow.connect(wowG).connect(delay.delayTime);
        const flutter = ctx.createOscillator();
        flutter.frequency.value = 6.3;
        const flG = ctx.createGain();
        flG.gain.value = 0.00022;
        flutter.connect(flG).connect(delay.delayTime);
        extras.push(wow, flutter);
        chain(this.biquad("highpass", 110), this.biquad("lowpass", 6200), this.biquad("peaking", 250, 0.8, 2.5), delay, this.shaper(1.4));
        extras.push(this.noiseBed(0.012, 3500, 12000, output));
        break;
      }
      case "phone": {
        chain(this.biquad("highpass", 420), this.biquad("lowpass", 3300), this.biquad("peaking", 1400, 1, 5), this.shaper(2.6));
        extras.push(this.noiseBed(0.006, 1000, 4000, output));
        break;
      }
      case "pa": {
        const hp = this.biquad("highpass", 520);
        const lp = this.biquad("lowpass", 2900);
        const sh = this.shaper(4.5);
        input.connect(hp).connect(lp).connect(sh);
        sh.connect(output);
        const d = ctx.createDelay(1);
        d.delayTime.value = 0.14;
        const fb = ctx.createGain();
        fb.gain.value = 0.32;
        sh.connect(d).connect(fb).connect(d);
        fb.connect(output);
        break;
      }
      case "echo": {
        input.connect(output);
        const d = ctx.createDelay(2);
        d.delayTime.value = 0.46;
        const fb = ctx.createGain();
        fb.gain.value = 0.46;
        const lp = this.biquad("lowpass", 2400);
        const wet = ctx.createGain();
        wet.gain.value = 0.55;
        input.connect(d).connect(lp).connect(fb).connect(d);
        lp.connect(wet).connect(output);
        break;
      }
      case "room": {
        input.connect(output);
        const conv = ctx.createConvolver();
        conv.buffer = this.irRoom;
        const wet = ctx.createGain();
        wet.gain.value = 0.16;
        input.connect(conv).connect(wet).connect(output);
        break;
      }
      default:
        input.connect(output);
    }
    return { input, output, extras };
  }
}
