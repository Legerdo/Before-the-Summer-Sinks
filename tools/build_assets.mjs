// Merge per-kind manifests into public/data/assets.json (what the engine and the story compiler read).
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1")), "..");
const D = (f) => path.join(ROOT, "public", "data", f);
const read = (f, d) => (fs.existsSync(D(f)) ? JSON.parse(fs.readFileSync(D(f), "utf8")) : d);

const images = read("images.json", { bg: {}, cg: {} });
const bgm = read("bgm.json", {});
const sfx = read("sfx.json", { amb: {}, se: {} });
const chars = read("chars.json", {});
const voice = read("voice.json", {});
// display settings for characters with sprites come from the single character registry
const registry = JSON.parse(fs.readFileSync(path.join(ROOT, "story", "characters.json"), "utf8"));
const charConf = {};
for (const c of Object.values(registry)) {
  if (!c.sprite) continue;
  charConf[c.id] = { name: c.name, color: c.color, scale: c.sprite.scale, y: c.sprite.y, defaultPose: c.sprite.defaultPose };
}
const credits = JSON.parse(fs.readFileSync(path.join(ROOT, "story", "credits.json"), "utf8"));
const out = { bg: images.bg, cg: images.cg, bgm, amb: sfx.amb, se: sfx.se, chars, charConf, voice, credits };

// sanity: every referenced file must exist
const missing = [];
for (const id of Object.keys(charConf)) {
  if (!chars[id]) missing.push(`sprite layers for "${id}" (run: python tools/img/build_sprites.py ${id})`);
  else if (!chars[id].bodies[charConf[id].defaultPose]) missing.push(`defaultPose "${charConf[id].defaultPose}" of ${id}`);
}
const check = (src) => { if (!fs.existsSync(path.join(ROOT, "public", src))) missing.push(src); };
for (const k of ["bg", "cg"]) for (const v of Object.values(out[k])) { check(v.src); if (v.thumb) check(v.thumb); }
for (const v of Object.values(bgm)) check(v.src);
for (const k of ["amb", "se"]) for (const v of Object.values(out[k])) check(v.src);
for (const c of Object.values(chars)) {
  for (const b of Object.values(c.bodies)) check(b);
  for (const f of Object.values(c.faces)) { check(f.face.src); if (f.eyes) check(f.eyes.src); for (const m of f.mouth) check(m.src); }
}
for (const v of Object.values(voice)) check(v.src);
fs.writeFileSync(D("assets.json"), JSON.stringify(out), "utf8");
console.log(`assets: bg ${Object.keys(out.bg).length}, cg ${Object.keys(out.cg).length}, bgm ${Object.keys(bgm).length}, amb ${Object.keys(out.amb).length}, se ${Object.keys(out.se).length}, chars ${Object.keys(chars).length}, voice ${Object.keys(voice).length}`);
if (missing.length) {
  console.error(`MISSING ${missing.length} files:`, missing.slice(0, 20));
  process.exit(1);
}
