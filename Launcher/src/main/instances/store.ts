import { randomUUID } from "node:crypto"
import { mkdir, readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { InstalledMod, Instance, Settings } from "@shared/types"
import type { LauncherPaths } from "../paths"
import { readModIndex, writeModIndex } from "../modrinth/api"

export const DEFAULT_SETTINGS: Settings = {
	memoryMb: 4096,
	gcPreset: "g1",
	windowWidth: 1280,
	windowHeight: 720,
	closeOnLaunch: false,
	extraJvmArgs: "",
}

export class InstanceStore {
	constructor(private readonly paths: LauncherPaths) {}

	private file(id: string): string {
		return join(this.paths.instance(id), "instance.json")
	}

	async list(): Promise<Instance[]> {
		const entries = await readdir(this.paths.instances, { withFileTypes: true }).catch(() => [])
		const instances: Instance[] = []
		for (const entry of entries) {
			if (entry.isDirectory()) {
				const instance = await this.get(entry.name).catch(() => undefined)
				if (instance) {
					instances.push(instance)
				}
			}
		}
		return instances.sort((a, b) => (b.lastPlayed ?? b.created) - (a.lastPlayed ?? a.created))
	}

	async get(id: string): Promise<Instance> {
		return JSON.parse(await readFile(this.file(id), "utf8")) as Instance
	}

	async save(instance: Instance): Promise<void> {
		await mkdir(this.paths.gameDirectory(instance.id), { recursive: true })
		await writeFile(this.file(instance.id), JSON.stringify(instance, null, "\t"))
	}

	async create(fields: Omit<Instance, "id" | "created">): Promise<Instance> {
		const instance: Instance = { ...fields, id: randomUUID(), created: Date.now() }
		await this.save(instance)
		return instance
	}

	async remove(id: string): Promise<void> {
		await rm(this.paths.instance(id), { recursive: true, force: true })
	}

	modsDirectory(id: string): string {
		return join(this.paths.gameDirectory(id), "mods")
	}

	async listMods(id: string): Promise<InstalledMod[]> {
		const directory = this.modsDirectory(id)
		const names = await readdir(directory).catch(() => [] as string[])
		const mods: InstalledMod[] = []
		for (const name of names) {
			if (name.endsWith(".jar") || name.endsWith(".jar.disabled")) {
				const enabled = name.endsWith(".jar")
				mods.push({ fileName: enabled ? name : name.slice(0, -".disabled".length), enabled, sizeBytes: (await stat(join(directory, name))).size })
			}
		}
		return mods.sort((a, b) => a.fileName.localeCompare(b.fileName))
	}

	async setModEnabled(id: string, fileName: string, enabled: boolean): Promise<void> {
		const directory = this.modsDirectory(id)
		const from = join(directory, enabled ? `${fileName}.disabled` : fileName)
		const to = join(directory, enabled ? fileName : `${fileName}.disabled`)
		await rename(from, to)
	}

	async deleteMod(id: string, fileName: string): Promise<void> {
		const directory = this.modsDirectory(id)
		await rm(join(directory, fileName), { force: true })
		await rm(join(directory, `${fileName}.disabled`), { force: true })
		const index = await readModIndex(this.paths.gameDirectory(id))
		delete index[fileName]
		await writeModIndex(this.paths.gameDirectory(id), index)
	}
}

export class SettingsStore {
	constructor(private readonly path: string) {}

	async get(): Promise<Settings> {
		try {
			return { ...DEFAULT_SETTINGS, ...(JSON.parse(await readFile(this.path, "utf8")) as Partial<Settings>) }
		} catch {
			return { ...DEFAULT_SETTINGS }
		}
	}

	async save(settings: Settings): Promise<void> {
		await writeFile(this.path, JSON.stringify(settings, null, "\t"))
	}
}
