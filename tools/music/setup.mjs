// Materialize track folders (song.json per track) inside a music session folder.
// Usage: node setup.mjs <sessionDir>
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const session = path.resolve(process.argv[2]);
const listFile = process.argv[3] || "tracks.json";
const tracks = JSON.parse(fs.readFileSync(path.join(HERE, listFile), "utf8"));
fs.mkdirSync(session, { recursive: true });
for (const t of tracks) {
  const dir = path.join(session, t.dir);
  fs.mkdirSync(dir, { recursive: true });
  const song = { title: t.title, prompt: t.prompt, lyrics: t.instrumental ? "" : t.lyrics, seed: t.seed, instrumental: t.instrumental, id: t.id };
  const p = path.join(dir, "song.json");
  const prev = fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null;
  const next = JSON.stringify(song, null, 2);
  if (prev !== next) {
    if (fs.existsSync(path.join(dir, "job.json"))) {
      console.log(`${t.dir}: already submitted, song.json left untouched`);
      continue;
    }
    fs.writeFileSync(p, next, "utf8");
    console.log(`${t.dir}: song.json written`);
  }
}
console.log(tracks.map((t) => path.join(session, t.dir)).join("\n"));
