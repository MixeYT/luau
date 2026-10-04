import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import AdmZip from "adm-zip"
import { downloadAll, downloadFile, fetchJson, type DownloadTask, type ProgressCallback } from "../http"
import type { LauncherPaths } from "../paths"
import { mergeVersions, resolveLibraries, type Environment, type ResolvedLibrary, type VersionJson, type VersionManifest } from "./versions"

export const VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
export const FABRIC_META_URL = "https://meta.fabricmc.net/v2"
const RESOURCES_URL = "https://resources.download.minecraft.net"

export interface InstallTarget {
	gameVersion: string
	loader: "vanilla" | "fabric"
	loaderVersion?: string
}

export interface InstalledVersion {
	version: VersionJson
	libraries: ResolvedLibrary[]
	clientJar: string
	nativesDirectory: string
	loggingConfig?: string
}

export type InstallProgress = (task: string, done: number, total: number) => void

let manifestCache: VersionManifest | undefined

export async function getVersionManifest(): Promise<VersionManifest> {
	manifestCache ??= await fetchJson<VersionManifest>(VERSION_MANIFEST_URL)
	return manifestCache
}

async function readCachedJson<T>(path: string): Promise<T | undefined> {
	try {
		return JSON.parse(await readFile(path, "utf8")) as T
	} catch {
		return undefined
	}
}

async function writeJson(path: string, data: unknown): Promise<void> {
	await mkdir(dirname(path), { recursive: true })
	await writeFile(path, JSON.stringify(data, null, "\t"))
}

export async function getVanillaVersion(paths: LauncherPaths, gameVersion: string): Promise<VersionJson> {
	const cached = await readCachedJson<VersionJson>(paths.versionJson(gameVersion))
	if (cached) {
		return cached
	}
	const entry = (await getVersionManifest()).versions.find((version) => version.id === gameVersion)
	if (!entry) {
		throw new Error(`Unknown Minecraft version ${gameVersion}`)
	}
	await downloadFile({ url: entry.url, path: paths.versionJson(gameVersion), sha1: entry.sha1 })
	return JSON.parse(await readFile(paths.versionJson(gameVersion), "utf8")) as VersionJson
}

export async function latestFabricLoader(gameVersion: string): Promise<string> {
	const loaders = await fetchJson<{ loader: { version: string; stable: boolean } }[]>(`${FABRIC_META_URL}/versions/loader/${gameVersion}`)
	const stable = loaders.find((entry) => entry.loader.stable) ?? loaders[0]
	if (!stable) {
		throw new Error(`Fabric does not support Minecraft ${gameVersion}`)
	}
	return stable.loader.version
}

export async function getFabricVersion(paths: LauncherPaths, gameVersion: string, loaderVersion: string): Promise<VersionJson> {
	const id = `fabric-loader-${loaderVersion}-${gameVersion}`
	const cached = await readCachedJson<VersionJson>(paths.versionJson(id))
	if (cached) {
		return cached
	}
	const profile = await fetchJson<VersionJson>(`${FABRIC_META_URL}/versions/loader/${gameVersion}/${loaderVersion}/profile/json`)
	await writeJson(paths.versionJson(id), profile)
	return profile
}

export async function resolveVersion(paths: LauncherPaths, target: InstallTarget): Promise<VersionJson> {
	const vanilla = await getVanillaVersion(paths, target.gameVersion)
	if (target.loader === "vanilla") {
		return vanilla
	}
	const loaderVersion = target.loaderVersion ?? (await latestFabricLoader(target.gameVersion))
	return mergeVersions(vanilla, await getFabricVersion(paths, target.gameVersion, loaderVersion))
}

function extractNatives(library: ResolvedLibrary, librariesRoot: string, destination: string): void {
	const zip = new AdmZip(join(librariesRoot, library.path))
	for (const entry of zip.getEntries()) {
		const excluded = entry.entryName.startsWith("META-INF/") || library.exclude.some((prefix) => entry.entryName.startsWith(prefix))
		const isLibrary = /\.(dll|so|dylib|jnilib)$/.test(entry.entryName)
		if (!entry.isDirectory && !excluded && isLibrary) {
			zip.extractEntryTo(entry, destination, false, true)
		}
	}
}

export async function installVersion(paths: LauncherPaths, target: InstallTarget, environment: Environment, onProgress?: InstallProgress): Promise<InstalledVersion> {
	const version = await resolveVersion(paths, target)
	const libraries = resolveLibraries(version.libraries, environment)
	const report = (task: string): ProgressCallback => (done, total) => onProgress?.(task, done, total)

	const vanillaId = target.gameVersion
	const tasks: DownloadTask[] = libraries.map((library) => ({ url: library.url, path: join(paths.libraries, library.path), sha1: library.sha1, size: library.size }))
	const client = version.downloads?.client
	if (client) {
		tasks.push({ url: client.url, path: paths.clientJar(vanillaId), sha1: client.sha1, size: client.size })
	}
	const logging = version.logging?.client
	const loggingConfig = logging ? join(paths.assets, "log_configs", logging.file.id) : undefined
	if (logging && loggingConfig) {
		tasks.push({ url: logging.file.url, path: loggingConfig, sha1: logging.file.sha1 })
	}
	await downloadAll(tasks, report("Biblioteki"))

	if (version.assetIndex) {
		const indexPath = join(paths.assets, "indexes", `${version.assetIndex.id}.json`)
		await downloadFile({ url: version.assetIndex.url, path: indexPath, sha1: version.assetIndex.sha1 })
		const index = JSON.parse(await readFile(indexPath, "utf8")) as { objects: Record<string, { hash: string; size: number }> }
		const assets = Object.values(index.objects).map(({ hash, size }) => ({
			url: `${RESOURCES_URL}/${hash.slice(0, 2)}/${hash}`,
			path: join(paths.assets, "objects", hash.slice(0, 2), hash),
			sha1: hash,
			size,
		}))
		await downloadAll(assets, report("Zasoby gry"), 32)
	}

	const nativesDirectory = paths.natives(version.id)
	await mkdir(nativesDirectory, { recursive: true })
	for (const library of libraries.filter((entry) => entry.native)) {
		extractNatives(library, paths.libraries, nativesDirectory)
	}

	return { version, libraries, clientJar: paths.clientJar(vanillaId), nativesDirectory, loggingConfig }
}
