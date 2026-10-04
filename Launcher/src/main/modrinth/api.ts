import { mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { ModSearchHit } from "@shared/types"
import { downloadFile, fetchJson } from "../http"

export const MODRINTH_API = "https://api.modrinth.com/v2"

// Mods that make the game run faster without changing how it plays.
export const OPTIMIZATION_MODS = [
	"fabric-api",
	"sodium",
	"lithium",
	"ferrite-core",
	"immediatelyfast",
	"entityculling",
	"modernfix",
	"moreculling",
	"dynamic-fps",
	"krypton",
	"sodium-extra",
	"reeses-sodium-options",
]

export interface ModrinthFile {
	url: string
	filename: string
	primary: boolean
	size: number
	hashes: { sha1: string; sha512: string }
}

export interface ModrinthVersion {
	id: string
	project_id: string
	version_number: string
	date_published: string
	loaders: string[]
	game_versions: string[]
	files: ModrinthFile[]
	dependencies: { project_id: string | null; version_id: string | null; dependency_type: "required" | "optional" | "incompatible" | "embedded" }[]
}

export interface ModIndexEntry {
	projectId: string
	versionId: string
	url: string
	sha1: string
	sha512: string
	size: number
}

export type ModIndex = Record<string, ModIndexEntry>

type JsonFetcher = <T>(url: string) => Promise<T>

export function searchUrl(query: string, gameVersion: string, loader: string, limit = 30): string {
	const facets = [["project_type:mod"], [`versions:${gameVersion}`], [`categories:${loader}`]]
	const parameters = new URLSearchParams({ query, limit: String(limit), index: "relevance", facets: JSON.stringify(facets) })
	return `${MODRINTH_API}/search?${parameters}`
}

export function projectVersionsUrl(project: string, gameVersion: string, loader: string): string {
	const parameters = new URLSearchParams({ loaders: JSON.stringify([loader]), game_versions: JSON.stringify([gameVersion]) })
	return `${MODRINTH_API}/project/${encodeURIComponent(project)}/version?${parameters}`
}

export class ModrinthClient {
	constructor(private readonly getJson: JsonFetcher = fetchJson) {}

	async search(query: string, gameVersion: string, loader: string): Promise<ModSearchHit[]> {
		const result = await this.getJson<{ hits: { project_id: string; slug: string; title: string; description: string; icon_url?: string; downloads: number; author: string }[] }>(searchUrl(query, gameVersion, loader))
		return result.hits.map((hit) => ({ projectId: hit.project_id, slug: hit.slug, title: hit.title, description: hit.description, iconUrl: hit.icon_url || undefined, downloads: hit.downloads, author: hit.author }))
	}

	async latestVersion(project: string, gameVersion: string, loader: string): Promise<ModrinthVersion | undefined> {
		const versions = await this.getJson<ModrinthVersion[]>(projectVersionsUrl(project, gameVersion, loader))
		return versions.sort((a, b) => b.date_published.localeCompare(a.date_published))[0]
	}

	// Picks the newest compatible version and pulls in every required dependency once.
	async resolve(projects: string[], gameVersion: string, loader: string, skipped: string[] = []): Promise<ModrinthVersion[]> {
		const resolved = new Map<string, ModrinthVersion>()
		const queue = [...projects]
		while (queue.length) {
			const project = queue.shift()!
			if ([...resolved.values()].some((version) => version.project_id === project) || resolved.has(project)) {
				continue
			}
			const version = await this.latestVersion(project, gameVersion, loader).catch(() => undefined)
			if (!version) {
				skipped.push(project)
				continue
			}
			if ([...resolved.values()].some((existing) => existing.project_id === version.project_id)) {
				continue
			}
			resolved.set(project, version)
			for (const dependency of version.dependencies) {
				if (dependency.dependency_type === "required" && dependency.project_id) {
					queue.push(dependency.project_id)
				}
			}
		}
		return [...resolved.values()]
	}
}

export function primaryFile(version: ModrinthVersion): ModrinthFile {
	return version.files.find((file) => file.primary) ?? version.files[0]
}

export async function readModIndex(gameDirectory: string): Promise<ModIndex> {
	try {
		return JSON.parse(await readFile(join(gameDirectory, "mods", ".mixe-index.json"), "utf8")) as ModIndex
	} catch {
		return {}
	}
}

export async function writeModIndex(gameDirectory: string, index: ModIndex): Promise<void> {
	await mkdir(join(gameDirectory, "mods"), { recursive: true })
	await writeFile(join(gameDirectory, "mods", ".mixe-index.json"), JSON.stringify(index, null, "\t"))
}

export async function installVersions(gameDirectory: string, versions: ModrinthVersion[]): Promise<string[]> {
	const index = await readModIndex(gameDirectory)
	const installed: string[] = []
	for (const version of versions) {
		const file = primaryFile(version)
		for (const [name, entry] of Object.entries(index)) {
			if (entry.projectId === version.project_id && name !== file.filename) {
				delete index[name]
				await rm(join(gameDirectory, "mods", name), { force: true })
			}
		}
		await downloadFile({ url: file.url, path: join(gameDirectory, "mods", file.filename), sha1: file.hashes.sha1, size: file.size })
		index[file.filename] = { projectId: version.project_id, versionId: version.id, url: file.url, sha1: file.hashes.sha1, sha512: file.hashes.sha512, size: file.size }
		installed.push(file.filename)
	}
	await writeModIndex(gameDirectory, index)
	return installed
}
