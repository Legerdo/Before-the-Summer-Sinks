// Electron shell: serves the built game from a privileged app:// scheme (so fetch/decodeAudioData,
// localStorage and relative asset URLs behave exactly like on the web) and exposes a tiny window API.
const { app, BrowserWindow, protocol, net, ipcMain, Menu, screen } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const { pathToFileURL } = require("node:url");

// VN_DIST / VN_USER_DATA let QA run an isolated instance next to a player's session.
const DIST = process.env.VN_DIST ? path.resolve(process.env.VN_DIST) : path.join(__dirname, "..", "dist");
if (process.env.VN_USER_DATA) app.setPath("userData", path.resolve(process.env.VN_USER_DATA));
const PREFS = () => path.join(app.getPath("userData"), "window.json");

protocol.registerSchemesAsPrivileged([
  { scheme: "app", privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true, codeCache: true } },
]);
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
// QA only: allow attaching an automation client when explicitly requested.
if (process.env.VN_DEBUG_PORT) app.commandLine.appendSwitch("remote-debugging-port", String(process.env.VN_DEBUG_PORT));

function readPrefs() {
  try {
    return JSON.parse(fs.readFileSync(PREFS(), "utf8"));
  } catch {
    return { width: 1600, height: 900, fullscreen: false };
  }
}

function writePrefs(p) {
  try {
    fs.mkdirSync(path.dirname(PREFS()), { recursive: true });
    fs.writeFileSync(PREFS(), JSON.stringify(p));
  } catch (e) {
    console.error("prefs", e);
  }
}

let win = null;
let prefs = null;

function createWindow() {
  prefs = readPrefs();
  const wa = screen.getPrimaryDisplay().workAreaSize;
  const w = Math.min(prefs.width || 1600, wa.width);
  const h = Math.min(prefs.height || 900, wa.height);
  win = new BrowserWindow({
    width: w,
    height: h,
    minWidth: 960,
    minHeight: 540,
    useContentSize: true,
    backgroundColor: "#000000",
    title: "여름이 가라앉기 전에",
    icon: path.join(__dirname, "..", "dist", "icon.png"),
    fullscreen: !!prefs.fullscreen,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });
  // no forced aspect ratio: the stage letterboxes itself, and Windows would apply the ratio to the frame
  win.once("ready-to-show", () => win.show());
  win.on("enter-full-screen", () => { prefs.fullscreen = true; writePrefs(prefs); });
  win.on("leave-full-screen", () => { prefs.fullscreen = false; writePrefs(prefs); });
  // external links never open inside the game window
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith("app://")) e.preventDefault(); });
  win.loadURL("app://game/index.html");
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  protocol.handle("app", (req) => {
    const u = new URL(req.url);
    let rel = decodeURIComponent(u.pathname).replace(/^\/+/, "");
    if (!rel) rel = "index.html";
    const file = path.normalize(path.join(DIST, rel));
    if (!file.startsWith(DIST)) return new Response("forbidden", { status: 403 });
    if (!fs.existsSync(file)) return new Response("not found", { status: 404 });
    return net.fetch(pathToFileURL(file).toString());
  });
  ipcMain.on("vn:quit", () => app.quit());
  ipcMain.on("vn:fullscreen", (_e, on) => win && win.setFullScreen(!!on));
  ipcMain.on("vn:isFullscreen", (e) => { e.returnValue = !!(win && win.isFullScreen()); });
  ipcMain.on("vn:size", (_e, w, h) => {
    if (!win) return;
    if (win.isFullScreen()) win.setFullScreen(false);
    win.setContentSize(Math.round(w), Math.round(h));
    win.center();
    prefs.width = w;
    prefs.height = h;
    writePrefs(prefs);
  });
  createWindow();
});

app.on("window-all-closed", () => app.quit());
