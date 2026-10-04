// Shared data types for the compiled story, asset manifests and runtime state.

export type Expr = string;

export interface SetOp {
  v: string;
  op: "=" | "+=" | "-=";
  e: Expr;
}

export interface ChoiceOption {
  text: string;
  target: string;
  set: SetOp[];
  cond?: Expr;
}

export interface SayIns {
  op: "say";
  id: string;
  text: string;
  who?: string;
  name?: string;
  expr?: string;
  voice?: string;
  cond?: Expr;
}

export interface ChoiceIns {
  op: "choice";
  id: string;
  options: ChoiceOption[];
  cond?: Expr;
}

export type ArgVal = string | number | boolean;

export interface CmdIns {
  op: string;
  pos: ArgVal[];
  kv: Record<string, ArgVal>;
  cond?: Expr;
}

export interface RawIns {
  op: string;
  [k: string]: unknown;
}

export interface Story {
  labels: Record<string, number>;
  code: RawIns[];
  srcmap: string[];
  first: string;
}

export interface LayerRect {
  src: string;
  rect: [number, number, number, number];
}

export interface FaceSet {
  face: LayerRect;
  eyes: LayerRect | null;
  mouth: LayerRect[];
}

export interface CharSprites {
  w: number;
  h: number;
  bodies: Record<string, string>;
  faces: Record<string, FaceSet>;
}

export interface BgmMeta {
  title: string;
  src: string;
  loop: boolean;
  loopStart?: number;
  loopEnd?: number;
  duration: number;
}

export interface SoundMeta {
  src: string;
  vol?: number;
  loop?: boolean;
  title?: string;
}

export interface ImageMeta {
  src: string;
  title?: string;
  thumb?: string;
}

export interface Assets {
  bg: Record<string, ImageMeta>;
  cg: Record<string, ImageMeta>;
  bgm: Record<string, BgmMeta>;
  amb: Record<string, SoundMeta>;
  se: Record<string, SoundMeta>;
  chars: Record<string, CharSprites>;
  charConf: Record<string, { name: string; color: string; scale: number; y: number; defaultPose: string }>;
  voice: Record<string, { src: string; dur: number }>;
  credits: { title: string; subtitle: string; sections: { h: string; lines: string[] }[]; outro: string[] };
}

export interface CharState {
  id: string;
  pose: string;
  expr: string;
  x: number; // 0..1 across the stage
  z: number;
  flip?: boolean;
}

export interface SceneState {
  bg: string | null;
  bgZoom: number;
  bgX: number;
  bgY: number;
  cg: string | null;
  chars: CharState[];
  bgm: string | null;
  bgmVol: number;
  amb: string[];
  sfxloop: string | null;
  fx: Record<string, number>;
  light: string;
  letterbox: boolean;
  sepia: boolean;
  blur: number;
  textbox: boolean;
  voicefx: string;
  camera: { zoom: number; x: number; y: number };
  chapter: string;
  date: string;
  tint?: string;
}

export interface BacklogEntry {
  name?: string;
  who?: string;
  text: string;
  voice?: string;
  voicefx?: string;
  choice?: boolean;
}

export interface Snapshot {
  pc: number;
  vars: Record<string, number>;
  scene: SceneState;
  backlog: BacklogEntry[];
  callStack: number[];
}

export interface SaveSlot {
  version: number;
  time: number;
  chapter: string;
  text: string;
  thumb: string | null;
  snap: Snapshot;
  playTime: number;
}
