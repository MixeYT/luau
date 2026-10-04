import { join } from "node:path"
import { app, BrowserWindow, shell } from "electron"
import { registerIpc } from "./ipc"
import { createPaths } from "./paths"

function createWindow(): void {
	const window = new BrowserWindow({
		width: 1180,
		height: 720,
		minWidth: 960,
		minHeight: 600,
		backgroundColor: "#0d0f17",
		title: "Mixe Launcher",
		autoHideMenuBar: true,
		show: false,
		webPreferences: {
			preload: join(__dirname, "../preload/index.js"),
			contextIsolation: true,
			nodeIntegration: false,
			sandbox: true,
		},
	})

	window.once("ready-to-show", () => window.show())
	window.webContents.setWindowOpenHandler(({ url }) => {
		void shell.openExternal(url)
		return { action: "deny" }
	})

	registerIpc(window, createPaths(join(app.getPath("appData"), "MixeLauncher")))

	if (process.env.ELECTRON_RENDERER_URL) {
		void window.loadURL(process.env.ELECTRON_RENDERER_URL)
	} else {
		void window.loadFile(join(__dirname, "../renderer/index.html"))
	}
}

app.whenReady().then(createWindow)
app.on("window-all-closed", () => app.quit())
