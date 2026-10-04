// Stage the built game + Electron shell and package a Windows x64 app folder with @electron/packager.
import fs from "node:fs";
import path from "node:path";
import { packager } from "@electron/packager";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1")), "..");
const STAGE = path.join(ROOT, "build", "app");
const WEB = path.resolve(ROOT, process.env.VN_WEB_DIR || "dist");
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));

fs.rmSync(STAGE, { recursive: true, force: true });
fs.mkdirSync(path.join(STAGE, "electron"), { recursive: true });
for (const f of ["main.cjs", "preload.cjs"]) fs.copyFileSync(path.join(ROOT, "electron", f), path.join(STAGE, "electron", f));
fs.cpSync(WEB, path.join(STAGE, "dist"), { recursive: true });
fs.writeFileSync(path.join(STAGE, "package.json"), JSON.stringify({
  name: "summer-sinks", productName: pkg.productName, version: pkg.version, description: pkg.description,
  main: "electron/main.cjs", author: "Kiro",
}, null, 2));

const out = await packager({
  dir: STAGE,
  out: path.join(ROOT, "release"),
  name: "SummerSinks",
  executableName: "SummerSinks",
  platform: "win32",
  arch: "x64",
  electronVersion: JSON.parse(fs.readFileSync(path.join(ROOT, "node_modules", "electron", "package.json"), "utf8")).version,
  icon: path.join(ROOT, "build", "icon.ico"),
  asar: true,
  overwrite: true,
  prune: false,
  appCopyright: "여름이 가라앉기 전에",
  win32metadata: { ProductName: pkg.productName, FileDescription: pkg.productName, CompanyName: "Kiro" },
});
console.log("packaged:", out);
