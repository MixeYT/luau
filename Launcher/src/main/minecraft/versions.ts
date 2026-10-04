export type OsName = "windows" | "osx" | "linux"

export interface Rule {
	action: "allow" | "disallow"
	os?: { name?: OsName; arch?: string; version?: string }
	features?: Record<string, boolean>
}

export interface Artifact {
	path?: string
	url: string
	sha1?: string
	size?: number
}

export interface Library {
	name: string
	url?: string
	sha1?: string
	size?: number
	downloads?: { artifact?: Artifact; classifiers?: Record<string, Artifact> }
	natives?: Partial<Record<OsName, string>>
	rules?: Rule[]
	extract?: { exclude?: string[] }
}

export type Argument = string | { rules: Rule[]; value: string | string[] }

export interface VersionJson {
	id: string
	inheritsFrom?: string
	mainClass: string
	type?: string
	assets?: string
	assetIndex?: { id: string; url: string; sha1: string; size: number; totalSize?: number }
	downloads?: { client?: Artifact }
	libraries: Library[]
	arguments?: { game?: Argument[]; jvm?: Argument[] }
	minecraftArguments?: string
	javaVersion?: { component: string; majorVersion: number }
	logging?: { client?: { argument: string; file: { id: string; url: string; sha1: string; size: number } } }
}

export interface VersionManifest {
	latest: { release: string; snapshot: string }
	versions: { id: string; type: string; url: string; sha1: string; releaseTime: string }[]
}

export interface Environment {
	os: OsName
	arch: string
	osVersion: string
	features: Record<string, boolean>
}

export function currentOs(): OsName {
	if (process.platform === "win32") {
		return "windows"
	}
	return process.platform === "darwin" ? "osx" : "linux"
}

export function currentEnvironment(features: Record<string, boolean> = {}): Environment {
	return { os: currentOs(), arch: process.arch === "ia32" ? "x86" : process.arch, osVersion: process.getSystemVersion?.() ?? "", features }
}

export function rulesAllow(rules: Rule[] | undefined, environment: Environment): boolean {
	if (!rules || rules.length === 0) {
		return true
	}
	let allowed = false
	for (const rule of rules) {
		const os = rule.os
		const osMatches =
			!os ||
			((!os.name || os.name === environment.os) &&
				(!os.arch || os.arch === environment.arch) &&
				(!os.version || new RegExp(os.version).test(environment.osVersion)))
		const featuresMatch = !rule.features || Object.entries(rule.features).every(([key, value]) => (environment.features[key] ?? false) === value)
		if (osMatches && featuresMatch) {
			allowed = rule.action === "allow"
		}
	}
	return allowed
}

export function mavenPath(name: string, extension = "jar"): string {
	const [coordinates, explicitExtension] = name.split("@")
	const [group, artifact, version, classifier] = coordinates.split(":")
	const file = `${artifact}-${version}${classifier ? `-${classifier}` : ""}.${explicitExtension ?? extension}`
	return [...group.split("."), artifact, version, file].join("/")
}

function libraryKey(library: Library): string {
	const [group, artifact, , classifier] = library.name.split(":")
	return `${group}:${artifact}:${classifier ?? ""}`
}

export function mergeVersions(parent: VersionJson, child: VersionJson): VersionJson {
	const childKeys = new Set(child.libraries.map(libraryKey))
	return {
		...parent,
		...child,
		inheritsFrom: undefined,
		mainClass: child.mainClass ?? parent.mainClass,
		assetIndex: child.assetIndex ?? parent.assetIndex,
		assets: child.assets ?? parent.assets,
		downloads: child.downloads ?? parent.downloads,
		javaVersion: child.javaVersion ?? parent.javaVersion,
		logging: child.logging ?? parent.logging,
		libraries: [...child.libraries, ...parent.libraries.filter((library) => !childKeys.has(libraryKey(library)))],
		arguments:
			parent.arguments || child.arguments
				? {
						game: [...(parent.arguments?.game ?? []), ...(child.arguments?.game ?? [])],
						jvm: [...(parent.arguments?.jvm ?? []), ...(child.arguments?.jvm ?? [])],
					}
				: undefined,
		minecraftArguments: child.minecraftArguments ?? parent.minecraftArguments,
	}
}

export interface ResolvedLibrary {
	path: string
	url: string
	sha1?: string
	size?: number
	classpath: boolean
	native: boolean
	exclude: string[]
}

// Turns the library list into concrete jar files for this machine: classpath jars and natives to extract.
export function resolveLibraries(libraries: Library[], environment: Environment): ResolvedLibrary[] {
	const resolved: ResolvedLibrary[] = []
	for (const library of libraries) {
		if (!rulesAllow(library.rules, environment)) {
			continue
		}
		const exclude = library.extract?.exclude ?? []
		const isNativeArtifact = /:natives-/.test(library.name)
		const artifact = library.downloads?.artifact
		if (artifact) {
			resolved.push({ path: artifact.path ?? mavenPath(library.name), url: artifact.url, sha1: artifact.sha1, size: artifact.size, classpath: true, native: isNativeArtifact, exclude })
		} else if (!library.natives) {
			const base = (library.url ?? "https://libraries.minecraft.net/").replace(/\/?$/, "/")
			const path = mavenPath(library.name)
			resolved.push({ path, url: base + path, sha1: library.sha1, size: library.size, classpath: true, native: isNativeArtifact, exclude })
		}

		const nativeClassifier = library.natives?.[environment.os]?.replace("${arch}", environment.arch === "x86" ? "32" : "64")
		const classifier = nativeClassifier ? library.downloads?.classifiers?.[nativeClassifier] : undefined
		if (classifier) {
			resolved.push({ path: classifier.path ?? mavenPath(`${library.name}:${nativeClassifier}`), url: classifier.url, sha1: classifier.sha1, size: classifier.size, classpath: false, native: true, exclude })
		}
	}
	return resolved
}
