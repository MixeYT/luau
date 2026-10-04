import { chmod, mkdir, symlink } from "node:fs/promises"
import { dirname, join } from "node:path"
import { downloadAll, fetchJson, type ProgressCallback } from "../http"

const RUNTIME_INDEX_URL = "https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"

interface RuntimeEntry {
	manifest: { sha1: string; size: number; url: string }
	version: { name: string; released: string }
}

type RuntimeIndex = Record<string, Record<string, RuntimeEntry[]>>

interface RuntimeManifest {
	files: Record<string, { type: "file" | "directory" | "link"; executable?: boolean; target?: string; downloads?: { raw: { sha1: string; size: number; url: string } } }>
}

export function runtimePlatform(platform: NodeJS.Platform = process.platform, arch: string = process.arch): string {
	if (platform === "win32") {
		return arch === "arm64" ? "windows-arm64" : arch === "ia32" ? "windows-x86" : "windows-x64"
	}
	if (platform === "darwin") {
		return arch === "arm64" ? "mac-os-arm64" : "mac-os"
	}
	return arch === "ia32" ? "linux-i386" : "linux"
}

export function javaExecutable(runtimeDirectory: string, platform: NodeJS.Platform = process.platform): string {
	if (platform === "win32") {
		return join(runtimeDirectory, "bin", "javaw.exe")
	}
	if (platform === "darwin") {
		return join(runtimeDirectory, "jre.bundle", "Contents", "Home", "bin", "java")
	}
	return join(runtimeDirectory, "bin", "java")
}

// Downloads the same Java build the official launcher uses for this Minecraft version.
export async function ensureJava(runtimesRoot: string, component = "jre-legacy", onProgress?: ProgressCallback): Promise<string> {
	const index = await fetchJson<RuntimeIndex>(RUNTIME_INDEX_URL)
	const entry = index[runtimePlatform()]?.[component]?.[0]
	if (!entry) {
		throw new Error(`No Java runtime ${component} for ${runtimePlatform()}`)
	}
	const directory = join(runtimesRoot, component)
	const manifest = await fetchJson<RuntimeManifest>(entry.manifest.url)
	const files = Object.entries(manifest.files)

	await mkdir(directory, { recursive: true })
	for (const [path, file] of files) {
		if (file.type === "directory") {
			await mkdir(join(directory, path), { recursive: true })
		}
	}
	const downloads = files.filter(([, file]) => file.type === "file" && file.downloads).map(([path, file]) => ({ url: file.downloads!.raw.url, path: join(directory, path), sha1: file.downloads!.raw.sha1, size: file.downloads!.raw.size }))
	await downloadAll(downloads, onProgress)

	if (process.platform !== "win32") {
		for (const [path, file] of files) {
			if (file.type === "file" && file.executable) {
				await chmod(join(directory, path), 0o755)
			} else if (file.type === "link" && file.target) {
				await mkdir(dirname(join(directory, path)), { recursive: true })
				await symlink(file.target, join(directory, path)).catch(() => undefined)
			}
		}
	}
	return javaExecutable(directory)
}
