// Persistent storage: save slots, global progress (read lines, unlocks, endings) and settings.

import type { SaveSlot } from "./types";

const NS = "sws1.";
export const SAVE_VERSION = 1;
export const SLOT_COUNT = 36;

export interface Settings {
  master: number;
  bgm: number;
  amb: number;
  se: number;
  voice: number;
  sys: number;
  textSpeed: number; // chars per second, 0 = instant
  autoSpeed: number; // 0..1 (higher = faster)
  skipUnread: boolean;
  voiceContinue: boolean;
  tbAlpha: number;
  fullscreen: boolean;
  windowSize: string;
}

export const DEFAULT_SETTINGS: Settings = {
  master: 0.85, bgm: 0.55, amb: 0.6, se: 0.7, voice: 0.95, sys: 0.5,
  textSpeed: 45, autoSpeed: 0.5, skipUnread: false, voiceContinue: false, tbAlpha: 0.78,
  fullscreen: false, windowSize: "1600x900",
};

export interface Global {
  read: string[];
  cgs: string[];
  bgms: string[];
  endings: string[];
  cleared: boolean;
  lastSlot: string | null;
  playTime: number;
}

function get<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(NS + key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

function put(key: string, v: unknown) {
  try {
    localStorage.setItem(NS + key, JSON.stringify(v));
  } catch (e) {
    console.error("storage failed", e);
    window.dispatchEvent(new CustomEvent("vn-error", { detail: `storage failed: ${key}` }));
  }
}

export class Store {
  settings: Settings = get("settings", DEFAULT_SETTINGS);
  private g: Global = get<Global>("global", { read: [], cgs: [], bgms: [], endings: [], cleared: false, lastSlot: null, playTime: 0 });
  private readSet = new Set(this.g.read);
  private dirty = false;

  constructor() {
    setInterval(() => this.flush(), 4000);
    addEventListener("beforeunload", () => this.flush());
  }

  get global() {
    return this.g;
  }

  saveSettings() {
    put("settings", this.settings);
  }

  isRead(id: string) {
    return this.readSet.has(id);
  }

  markRead(id: string) {
    if (this.readSet.has(id)) return;
    this.readSet.add(id);
    this.g.read.push(id);
    this.dirty = true;
  }

  unlock(kind: "cgs" | "bgms" | "endings", id: string) {
    if (this.g[kind].includes(id)) return;
    this.g[kind].push(id);
    this.dirty = true;
    this.flush();
  }

  setCleared() {
    this.g.cleared = true;
    this.dirty = true;
    this.flush();
  }

  addPlayTime(sec: number) {
    this.g.playTime += sec;
    this.dirty = true;
  }

  flush() {
    if (!this.dirty) return;
    this.dirty = false;
    put("global", this.g);
  }

  slotKey(slot: string) {
    return "save." + slot;
  }

  load(slot: string): SaveSlot | null {
    try {
      const raw = localStorage.getItem(NS + this.slotKey(slot));
      if (!raw) return null;
      const s = JSON.parse(raw) as SaveSlot;
      return s.version === SAVE_VERSION ? s : null;
    } catch {
      return null;
    }
  }

  write(slot: string, data: SaveSlot) {
    put(this.slotKey(slot), data);
    this.g.lastSlot = slot;
    this.dirty = true;
    this.flush();
  }

  remove(slot: string) {
    localStorage.removeItem(NS + this.slotKey(slot));
  }

  /** Most recent save across all slots (for "continue"). */
  latest(): { slot: string; data: SaveSlot } | null {
    let best: { slot: string; data: SaveSlot } | null = null;
    const slots = ["auto", "quick", ...Array.from({ length: SLOT_COUNT }, (_, i) => String(i + 1))];
    for (const s of slots) {
      const d = this.load(s);
      if (d && (!best || d.time > best.data.time)) best = { slot: s, data: d };
    }
    return best;
  }
}
