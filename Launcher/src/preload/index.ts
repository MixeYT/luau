import { contextBridge, ipcRenderer } from "electron"
import type { LauncherApi } from "@shared/types"

const invoke =
	(name: string) =>
	(...args: unknown[]) =>
		ipcRenderer.invoke(`launcher:${name}`, ...args)

function listen<T>(channel: string) {
	return (callback: (payload: T) => void) => {
		const listener = (_event: Electron.IpcRendererEvent, payload: T) => callback(payload)
		ipcRenderer.on(channel, listener)
		return () => {
			ipcRenderer.removeListener(channel, listener)
		}
	}
}

const methods = [
	"getVersions", "getSettings", "saveSettings",
	"listInstances", "createInstance", "deleteInstance", "openInstanceFolder", "launchInstance",
	"listMods", "setModEnabled", "deleteMod", "searchMods", "installMod", "applyOptimization",
	"exportModpack", "importModpack",
	"listAccounts", "addAccount", "selectAccount", "removeAccount",
] as const

const api = {
	...Object.fromEntries(methods.map((name) => [name, invoke(name)])),
	onDeviceCode: listen("launcher:deviceCode"),
	onProgress: listen("launcher:progress"),
	onLog: listen("launcher:log"),
} as unknown as LauncherApi

contextBridge.exposeInMainWorld("launcher", api)
