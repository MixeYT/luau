import { join } from "node:path"

export interface LauncherPaths {
	root: string
	versions: string
	libraries: string
	assets: string
	runtimes: string
	instances: string
	settings: string
	accounts: string
	versionJson(id: string): string
	clientJar(id: string): string
	natives(id: string): string
	instance(id: string): string
	gameDirectory(id: string): string
}

export function createPaths(root: string): LauncherPaths {
	return {
		root,
		versions: join(root, "versions"),
		libraries: join(root, "libraries"),
		assets: join(root, "assets"),
		runtimes: join(root, "runtimes"),
		instances: join(root, "instances"),
		settings: join(root, "settings.json"),
		accounts: join(root, "accounts.dat"),
		versionJson: (id) => join(root, "versions", id, `${id}.json`),
		clientJar: (id) => join(root, "versions", id, `${id}.jar`),
		natives: (id) => join(root, "versions", id, "natives"),
		instance: (id) => join(root, "instances", id),
		gameDirectory: (id) => join(root, "instances", id, "minecraft"),
	}
}
