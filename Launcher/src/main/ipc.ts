import { spawn } from "node:child_process"
import { BrowserWindow, dialog, ipcMain, safeStorage, shell } from "electron"
import AdmZip from "adm-zip"
import type { GameVersion, InstanceDraft, LogLine, OptimizeReport, ProgressEvent, Settings } from "@shared/types"
import { AccountStore } from "./auth/accounts"
import { MicrosoftAuth } from "./auth/microsoft"
import { InstanceStore, SettingsStore } from "./instances/store"
import { ensureJava } from "./minecraft/java"
import { buildLaunchArguments } from "./minecraft/launch"
import { getVersionManifest, installVersion, latestFabricLoader } from "./minecraft/installer"
import { currentEnvironment } from "./minecraft/versions"
import { installVersions, ModrinthClient, OPTIMIZATION_MODS } from "./modrinth/api"
import { exportModpack, installPackFiles, packTarget, readPackIndex } from "./modrinth/mrpack"
import type { LauncherPaths } from "./paths"

export function registerIpc(window: BrowserWindow, paths: LauncherPaths): void {
	const instances = new InstanceStore(paths)
	const settings = new SettingsStore(paths.settings)
	const accounts = new AccountStore(paths.accounts, {
		encrypt: (text) => (safeStorage.isEncryptionAvailable() ? safeStorage.encryptString(text) : Buffer.from(text)),
		decrypt: (data) => (safeStorage.isEncryptionAvailable() ? safeStorage.decryptString(data) : data.toString()),
	})
	const auth = new MicrosoftAuth()
	const modrinth = new ModrinthClient()

	const send = (channel: string, payload: unknown): void => {
		if (!window.isDestroyed()) {
			window.webContents.send(channel, payload)
		}
	}
	const progress = (task: string, done: number, total: number): void => send("launcher:progress", { task, done, total } satisfies ProgressEvent)
	const log = (line: LogLine): void => send("launcher:log", line)

	const handle = <A extends unknown[], R>(name: string, handler: (...args: A) => Promise<R>): void => {
		ipcMain.handle(`launcher:${name}`, (_event, ...args) => handler(...(args as A)))
	}

	async function optimize(instanceId: string): Promise<OptimizeReport> {
		const instance = await instances.get(instanceId)
		if (instance.loader !== "fabric") {
			throw new Error("Mody optymalizacyjne wymagają Fabric.")
		}
		const skipped: string[] = []
		progress("Szukam modów optymalizacyjnych", 0, 1)
		const versions = await modrinth.resolve(OPTIMIZATION_MODS, instance.gameVersion, "fabric", skipped)
		const installed = await installVersions(paths.gameDirectory(instance.id), versions)
		progress("Mody zainstalowane", 1, 1)
		return { installed, skipped }
	}

	handle("getVersions", async (): Promise<GameVersion[]> => {
		const manifest = await getVersionManifest()
		return manifest.versions.filter((version) => version.type === "release").map((version) => ({ id: version.id, type: "release" }))
	})
	handle("getSettings", () => settings.get())
	handle("saveSettings", (value: Settings) => settings.save(value))

	handle("listInstances", () => instances.list())
	handle("createInstance", async (draft: InstanceDraft) => {
		const loaderVersion = draft.loader === "fabric" ? await latestFabricLoader(draft.gameVersion) : undefined
		const instance = await instances.create({ name: draft.name, gameVersion: draft.gameVersion, loader: draft.loader, loaderVersion })
		if (draft.optimize && draft.loader === "fabric") {
			await optimize(instance.id)
		}
		return instance
	})
	handle("deleteInstance", (id: string) => instances.remove(id))
	handle("openInstanceFolder", async (id: string) => {
		await shell.openPath(paths.gameDirectory(id))
	})

	handle("launchInstance", async (id: string) => {
		const stored = await accounts.selected()
		if (!stored) {
			throw new Error("Najpierw zaloguj się kontem Microsoft.")
		}
		const account = await auth.refresh(stored)
		await accounts.save(account)
		const instance = await instances.get(id)
		const config = await settings.get()
		const environment = currentEnvironment({ has_custom_resolution: true, is_demo_user: false })

		const installed = await installVersion(paths, instance, environment, progress)
		const java = await ensureJava(paths.runtimes, installed.version.javaVersion?.component, (done, total) => progress("Java", done, total))
		const args = buildLaunchArguments({
			installed,
			java,
			profile: { username: account.username, uuid: account.uuid, accessToken: account.accessToken, xuid: account.xuid },
			gameDirectory: paths.gameDirectory(id),
			librariesRoot: paths.libraries,
			assetsRoot: paths.assets,
			memoryMb: instance.memoryMb ?? config.memoryMb,
			gcPreset: config.gcPreset,
			width: config.windowWidth,
			height: config.windowHeight,
			extraJvmArgs: config.extraJvmArgs.split(" ").filter(Boolean),
			environment,
		})

		log({ instanceId: id, line: `Uruchamiam ${installed.version.id} jako ${account.username}`, stream: "launcher" })
		const game = spawn(java, args, { cwd: paths.gameDirectory(id), detached: false })
		for (const stream of ["stdout", "stderr"] as const) {
			game[stream].setEncoding("utf8")
			game[stream].on("data", (chunk: string) => {
				for (const line of chunk.split(/\r?\n/).filter(Boolean)) {
					log({ instanceId: id, line, stream })
				}
			})
		}
		game.on("exit", (code) => {
			log({ instanceId: id, line: `Gra zamknięta (kod ${code})`, stream: "launcher" })
			if (config.closeOnLaunch && !window.isDestroyed()) {
				window.show()
			}
		})
		if (config.closeOnLaunch) {
			window.hide()
		}
		await instances.save({ ...instance, lastPlayed: Date.now() })
		progress("Gra uruchomiona", 1, 1)
	})

	handle("listMods", (id: string) => instances.listMods(id))
	handle("setModEnabled", (id: string, fileName: string, enabled: boolean) => instances.setModEnabled(id, fileName, enabled))
	handle("deleteMod", (id: string, fileName: string) => instances.deleteMod(id, fileName))
	handle("searchMods", async (id: string, query: string) => {
		const instance = await instances.get(id)
		return modrinth.search(query, instance.gameVersion, instance.loader === "fabric" ? "fabric" : "minecraft")
	})
	handle("installMod", async (id: string, projectId: string) => {
		const instance = await instances.get(id)
		const versions = await modrinth.resolve([projectId], instance.gameVersion, "fabric")
		if (!versions.length) {
			throw new Error("Ten mod nie ma wersji dla tej instancji.")
		}
		return installVersions(paths.gameDirectory(id), versions)
	})
	handle("applyOptimization", (id: string) => optimize(id))

	handle("exportModpack", async (id: string) => {
		const instance = await instances.get(id)
		const result = await dialog.showSaveDialog(window, { defaultPath: `${instance.name}.mrpack`, filters: [{ name: "Modrinth Modpack", extensions: ["mrpack"] }] })
		if (result.canceled || !result.filePath) {
			return null
		}
		await exportModpack(instance, paths.gameDirectory(id), result.filePath)
		return result.filePath
	})
	handle("importModpack", async () => {
		const result = await dialog.showOpenDialog(window, { properties: ["openFile"], filters: [{ name: "Modrinth Modpack", extensions: ["mrpack"] }] })
		if (result.canceled || !result.filePaths[0]) {
			return null
		}
		const zip = new AdmZip(result.filePaths[0])
		const index = readPackIndex(zip)
		const target = packTarget(index)
		const instance = await instances.create(target)
		await installPackFiles(zip, index, paths.gameDirectory(instance.id), (done, total) => progress("Pobieranie modpacka", done, total))
		return instance
	})

	handle("listAccounts", () => accounts.list())
	handle("addAccount", async () => {
		const account = await auth.loginWithDeviceCode((prompt) => {
			send("launcher:deviceCode", prompt)
			void shell.openExternal(prompt.verificationUri)
		})
		await accounts.save(account)
		return { id: account.id, username: account.username, uuid: account.uuid, selected: true }
	})
	handle("selectAccount", (id: string) => accounts.select(id))
	handle("removeAccount", (id: string) => accounts.remove(id))
}
