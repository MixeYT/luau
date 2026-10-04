import { mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises"
import { dirname, join, normalize, relative, sep } from "node:path"
import AdmZip from "adm-zip"
import type { Instance, Loader } from "@shared/types"
import { downloadAll } from "../http"
import { readModIndex, writeModIndex, type ModIndex } from "./api"

export interface MrpackFile {
	path: string
	hashes: { sha1: string; sha512: string }
	env?: { client: "required" | "optional" | "unsupported"; server: "required" | "optional" | "unsupported" }
	downloads: string[]
	fileSize: number
}

export interface MrpackIndex {
	formatVersion: 1
	game: "minecraft"
	versionId: string
	name: string
	summary?: string
	files: MrpackFile[]
	dependencies: Record<string, string>
}

export interface ImportedPack {
	name: string
	gameVersion: string
	loader: Loader
	loaderVersion?: string
}

// Folders that belong to the player, never to the modpack.
const SKIPPED_FOLDERS = new Set(["saves", "logs", "crash-reports", "screenshots", "downloads", ".fabric", "debug"])
const ALLOWED_DOWNLOAD_HOSTS = ["cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com"]

export function buildIndex(instance: Instance, mods: ModIndex, enabledMods: string[]): MrpackIndex {
	const dependencies: Record<string, string> = { minecraft: instance.gameVersion }
	if (instance.loader === "fabric" && instance.loaderVersion) {
		dependencies["fabric-loader"] = instance.loaderVersion
	}
	return {
		formatVersion: 1,
		game: "minecraft",
		versionId: "1.0.0",
		name: instance.name,
		summary: `Modpack zrobiony w Mixe Launcher (${instance.gameVersion})`,
		files: enabledMods
			.filter((name) => mods[name])
			.map((name) => ({
				path: `mods/${name}`,
				hashes: { sha1: mods[name].sha1, sha512: mods[name].sha512 },
				env: { client: "required", server: "required" },
				downloads: [mods[name].url],
				fileSize: mods[name].size,
			})),
		dependencies,
	}
}

async function collectOverrides(root: string, directory: string, zip: AdmZip, skip: Set<string>): Promise<void> {
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = join(directory, entry.name)
		const relativePath = relative(root, path).split(sep).join("/")
		if (skip.has(relativePath) || SKIPPED_FOLDERS.has(relativePath) || entry.name === ".mixe-index.json") {
			continue
		}
		if (entry.isDirectory()) {
			await collectOverrides(root, path, zip, skip)
		} else {
			zip.addFile(`overrides/${relativePath}`, await readFile(path))
		}
	}
}

export async function exportModpack(instance: Instance, gameDirectory: string, outputPath: string): Promise<void> {
	const mods = await readModIndex(gameDirectory)
	const modFiles = await readdir(join(gameDirectory, "mods")).catch(() => [] as string[])
	const enabled = modFiles.filter((name) => name.endsWith(".jar"))
	const index = buildIndex(instance, mods, enabled)

	const zip = new AdmZip()
	zip.addFile("modrinth.index.json", Buffer.from(JSON.stringify(index, null, "\t")))
	const fromModrinth = new Set(index.files.map((file) => file.path))
	await collectOverrides(gameDirectory, gameDirectory, zip, fromModrinth)
	await mkdir(dirname(outputPath), { recursive: true })
	await writeFile(outputPath, zip.toBuffer())
}

export function safeJoin(root: string, path: string): string {
	const target = normalize(join(root, path))
	if (!target.startsWith(normalize(root) + sep) || path.includes("..")) {
		throw new Error(`Unsafe path in modpack: ${path}`)
	}
	return target
}

export function readPackIndex(zip: AdmZip): MrpackIndex {
	const entry = zip.getEntry("modrinth.index.json")
	if (!entry) {
		throw new Error("To nie jest modpack .mrpack (brak modrinth.index.json)")
	}
	const index = JSON.parse(entry.getData().toString("utf8")) as MrpackIndex
	if (index.formatVersion !== 1 || index.game !== "minecraft") {
		throw new Error("Nieobsługiwana wersja formatu .mrpack")
	}
	return index
}

export function packTarget(index: MrpackIndex): ImportedPack {
	const loaderVersion = index.dependencies["fabric-loader"]
	if (!loaderVersion && Object.keys(index.dependencies).some((key) => key !== "minecraft")) {
		throw new Error("Ten modpack używa loadera, którego launcher jeszcze nie obsługuje (tylko Fabric i vanilla).")
	}
	return { name: index.name, gameVersion: index.dependencies.minecraft, loader: loaderVersion ? "fabric" : "vanilla", loaderVersion }
}

export async function installPackFiles(zip: AdmZip, index: MrpackIndex, gameDirectory: string, onProgress?: (done: number, total: number) => void): Promise<void> {
	const files = index.files.filter((file) => file.env?.client !== "unsupported")
	const tasks = files.map((file) => {
		const url = file.downloads.find((download) => ALLOWED_DOWNLOAD_HOSTS.includes(new URL(download).hostname))
		if (!url) {
			throw new Error(`Plik ${file.path} pochodzi z niedozwolonego źródła`)
		}
		return { url, path: safeJoin(gameDirectory, file.path), sha1: file.hashes.sha1, size: file.fileSize }
	})
	await downloadAll(tasks, onProgress)

	for (const prefix of ["overrides/", "client-overrides/"]) {
		for (const entry of zip.getEntries()) {
			if (entry.isDirectory || !entry.entryName.startsWith(prefix)) {
				continue
			}
			const target = safeJoin(gameDirectory, entry.entryName.slice(prefix.length))
			await mkdir(dirname(target), { recursive: true })
			await writeFile(target, entry.getData())
		}
	}

	const mods: ModIndex = await readModIndex(gameDirectory)
	for (const file of files) {
		if (file.path.startsWith("mods/")) {
			const name = file.path.slice("mods/".length)
			const size = (await stat(join(gameDirectory, file.path))).size
			mods[name] = { projectId: "", versionId: "", url: file.downloads[0], sha1: file.hashes.sha1, sha512: file.hashes.sha512, size }
		}
	}
	await writeModIndex(gameDirectory, mods)
}
