import { createHash } from "node:crypto"
import { mkdir, readFile, rename, writeFile } from "node:fs/promises"
import { dirname } from "node:path"

export const USER_AGENT = "MixeYT/mixe-launcher/0.1.0 (github.com/MixeYT/luau)"

const RETRIES = 3

export interface DownloadTask {
	url: string
	path: string
	sha1?: string
	size?: number
}

export type ProgressCallback = (done: number, total: number) => void

export async function fetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
	const response = await request(url, init)
	return (await response.json()) as T
}

export async function request(url: string, init: RequestInit = {}): Promise<Response> {
	let lastError: unknown
	for (let attempt = 0; attempt < RETRIES; attempt++) {
		try {
			const response = await fetch(url, { ...init, headers: { "User-Agent": USER_AGENT, ...(init.headers ?? {}) } })
			if (response.ok) {
				return response
			}
			lastError = new Error(`${init.method ?? "GET"} ${url} failed with ${response.status}: ${await response.text()}`)
			if (response.status < 500 && response.status !== 429) {
				break
			}
		} catch (error) {
			lastError = error
		}
		await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt))
	}
	throw lastError
}

export function sha1(data: Buffer): string {
	return createHash("sha1").update(data).digest("hex")
}

export function sha512(data: Buffer): string {
	return createHash("sha512").update(data).digest("hex")
}

async function isValid(task: DownloadTask): Promise<boolean> {
	try {
		const data = await readFile(task.path)
		if (task.sha1) {
			return sha1(data) === task.sha1
		}
		return task.size === undefined || data.length === task.size
	} catch {
		return false
	}
}

export async function downloadFile(task: DownloadTask): Promise<void> {
	if (await isValid(task)) {
		return
	}
	const data = Buffer.from(await (await request(task.url)).arrayBuffer())
	if (task.sha1 && sha1(data) !== task.sha1) {
		throw new Error(`Checksum mismatch for ${task.url}`)
	}
	await mkdir(dirname(task.path), { recursive: true })
	const temporary = `${task.path}.part`
	await writeFile(temporary, data)
	await rename(temporary, task.path)
}

export async function downloadAll(tasks: DownloadTask[], onProgress?: ProgressCallback, concurrency = 16): Promise<void> {
	const unique = [...new Map(tasks.map((task) => [task.path, task])).values()]
	let next = 0
	let done = 0
	onProgress?.(0, unique.length)

	async function worker(): Promise<void> {
		while (next < unique.length) {
			const task = unique[next++]
			await downloadFile(task)
			done++
			onProgress?.(done, unique.length)
		}
	}

	await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, worker))
}
