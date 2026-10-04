const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vnHost", {
  quit: () => ipcRenderer.send("vn:quit"),
  setFullscreen: (on) => ipcRenderer.send("vn:fullscreen", !!on),
  isFullscreen: () => ipcRenderer.sendSync("vn:isFullscreen"),
  setWindowSize: (w, h) => ipcRenderer.send("vn:size", w, h),
});
