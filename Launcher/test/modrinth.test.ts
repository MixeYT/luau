import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import AdmZip from "adm-zip"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { Instance } from "../src/shared/types"
import { sha1, sha512 } from "../src/main/http"
import { ModrinthClient, projectVersionsUrl, searchUrl, writeModIndex, type ModrinthVersion } from "../src/main/modrinth/api"
import { exportModpack, installPackFiles, packTarget, readPackIndex, safeJoin } from "../src/main/modrinth/mrpack"

function version(project: string, dependencies: string[] = [], date = "2024-01-01"): ModrinthVersion {
	return {
		id: `${project}-v`,
		project_id: project,
		version_number: "1.0",
		date_published: date,
		loaders: ["fabric"],
		game_versions: ["1.21.1"],
		files: [{ url: `https://cdn.modrinth.com/${project}.jar`, filename: `${project}.jar`, primary: true, size: 3, hashes: { sha1: "x", sha512: "y" } }],
		dependencies: dependencies.map((id) => ({ project_id: id, version_id: null, dependency_type: "required" as const })),
	}
}

describe("modrinth api", () => {
	it("builds search and version urls with facets", () => {
		const search = new URL(searchUrl("sodium", "1.21.1", "fabric"))
		expect(JSON.parse(search.searchParams.get("facets")!)).toEqual([["project_type:mod"], ["versions:1.21.1"], ["categories:fabric"]])
		const versions = new URL(projectVersionsUrl("sodium", "1.21.1", "fabric"))
		expect(versions.pathname).toBe("/v2/project/sodium/version")
		expect(versions.searchParams.get("loaders")).toBe('["fabric"]')
	})

	it("resolves required dependencies once and reports missing projects", async () => {
		const versions: Record<string, ModrinthVersion[]> = {
			sodium: [version("sodium", ["fabric-api"])],
			lithium: [version("lithium", ["fabric-api"])],
			"fabric-api": [version("fabric-api", [], "2023-01-01"), version("fabric-api", [], "2024-06-01")],
			missing: [],
		}
		const client = new ModrinthClient(async <T>(url: string) => {
			const project = new URL(url).pathname.split("/")[3]
			return versions[project] as T
		})
		const skipped: string[] = []
		const resolved = await client.resolve(["sodium", "lithium", "missing"], "1.21.1", "fabric", skipped)
		expect(resolved.map((entry) => entry.project_id).sort()).toEqual(["fabric-api", "lithium", "sodium"])
		expect(resolved.find((entry) => entry.project_id === "fabric-api")?.date_published).toBe("2024-06-01")
		expect(skipped).toEqual(["missing"])
	})
})

describe("mrpack", () => {
	afterEach(() => vi.unstubAllGlobals())

	it("rejects paths that escape the instance", () => {
		expect(() => safeJoin("/game", "../evil.jar")).toThrow()
		expect(() => safeJoin("/game", "mods/../../evil.jar")).toThrow()
		expect(safeJoin("/game", "mods/ok.jar")).toBe(join("/game", "mods/ok.jar"))
	})

	it("exports a modpack and imports it into a fresh instance", async () => {
		const source = await mkdtemp(join(tmpdir(), "mixe-source-"))
		const modBytes = Buffer.from("sodium-jar")
		await mkdir(join(source, "mods"), { recursive: true })
		await mkdir(join(source, "config"), { recursive: true })
		await mkdir(join(source, "saves", "World"), { recursive: true })
		await writeFile(join(source, "mods", "sodium.jar"), modBytes)
		await writeFile(join(source, "mods", "custom.jar"), Buffer.from("local-mod"))
		await writeFile(join(source, "mods", "old.jar.disabled"), Buffer.from("disabled"))
		await writeFile(join(source, "config", "sodium.json"), "{}")
		await writeFile(join(source, "saves", "World", "level.dat"), "world")
		await writeModIndex(source, { "sodium.jar": { projectId: "AANobbMI", versionId: "v1", url: "https://cdn.modrinth.com/data/AANobbMI/sodium.jar", sha1: sha1(modBytes), sha512: sha512(modBytes), size: modBytes.length } })

		const instance: Instance = { id: "i", name: "Mój Pack", gameVersion: "1.21.1", loader: "fabric", loaderVersion: "0.16.9", created: 0 }
		const packPath = join(source, "out", "pack.mrpack")
		await exportModpack(instance, source, packPath)

		const zip = new AdmZip(packPath)
		const index = readPackIndex(zip)
		expect(index.dependencies).toEqual({ minecraft: "1.21.1", "fabric-loader": "0.16.9" })
		expect(index.files.map((file) => file.path)).toEqual(["mods/sodium.jar"])
		const entries = zip.getEntries().map((entry) => entry.entryName)
		expect(entries).toContain("overrides/mods/custom.jar")
		expect(entries).toContain("overrides/config/sodium.json")
		expect(entries.some((entry) => entry.includes("saves"))).toBe(false)
		expect(entries.some((entry) => entry.includes(".mixe-index.json"))).toBe(false)

		expect(packTarget(index)).toEqual({ name: "Mój Pack", gameVersion: "1.21.1", loader: "fabric", loaderVersion: "0.16.9" })

		vi.stubGlobal("fetch", async () => new Response(modBytes))
		const target = await mkdtemp(join(tmpdir(), "mixe-target-"))
		await installPackFiles(zip, index, target)
		expect(await readFile(join(target, "mods", "sodium.jar"))).toEqual(modBytes)
		expect(await readFile(join(target, "mods", "custom.jar"), "utf8")).toBe("local-mod")
		expect(await readFile(join(target, "config", "sodium.json"), "utf8")).toBe("{}")
	})

	it("refuses downloads from unknown hosts", async () => {
		const zip = new AdmZip()
		const index = readPackIndexFrom(zip, { path: "mods/x.jar", downloads: ["https://evil.example.com/x.jar"] })
		await expect(installPackFiles(zip, index, await mkdtemp(join(tmpdir(), "mixe-evil-")))).rejects.toThrow(/niedozwolonego/)
	})
})

function readPackIndexFrom(zip: AdmZip, file: { path: string; downloads: string[] }) {
	zip.addFile(
		"modrinth.index.json",
		Buffer.from(JSON.stringify({ formatVersion: 1, game: "minecraft", versionId: "1", name: "x", files: [{ ...file, hashes: { sha1: "a", sha512: "b" }, fileSize: 1 }], dependencies: { minecraft: "1.21.1" } })),
	)
	return readPackIndex(zip)
}
