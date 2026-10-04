import { describe, expect, it } from "vitest"
import { mavenPath, mergeVersions, resolveLibraries, rulesAllow, type Environment, type VersionJson } from "../src/main/minecraft/versions"

const windows: Environment = { os: "windows", arch: "x64", osVersion: "10.0", features: { has_custom_resolution: true } }
const linux: Environment = { os: "linux", arch: "x64", osVersion: "6.1", features: {} }

describe("rules", () => {
	it("allows everything without rules", () => {
		expect(rulesAllow(undefined, windows)).toBe(true)
	})

	it("uses the last matching rule", () => {
		const rules = [{ action: "allow" as const }, { action: "disallow" as const, os: { name: "osx" as const } }]
		expect(rulesAllow(rules, windows)).toBe(true)
		expect(rulesAllow(rules, { ...windows, os: "osx" })).toBe(false)
	})

	it("matches features", () => {
		const rules = [{ action: "allow" as const, features: { has_custom_resolution: true } }]
		expect(rulesAllow(rules, windows)).toBe(true)
		expect(rulesAllow(rules, linux)).toBe(false)
	})
})

describe("maven paths", () => {
	it("builds library paths with classifiers and extensions", () => {
		expect(mavenPath("net.fabricmc:fabric-loader:0.16.9")).toBe("net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar")
		expect(mavenPath("org.lwjgl:lwjgl:3.3.3:natives-windows")).toBe("org/lwjgl/lwjgl/3.3.3/lwjgl-3.3.3-natives-windows.jar")
		expect(mavenPath("com.example:thing:1.0@zip")).toBe("com/example/thing/1.0/thing-1.0.zip")
	})
})

const vanilla: VersionJson = {
	id: "1.21.1",
	mainClass: "net.minecraft.client.main.Main",
	type: "release",
	assetIndex: { id: "17", url: "https://example/17.json", sha1: "a", size: 1 },
	downloads: { client: { url: "https://example/client.jar", sha1: "b", size: 2 } },
	javaVersion: { component: "java-runtime-delta", majorVersion: 21 },
	arguments: { game: ["--username", "${auth_player_name}"], jvm: ["-cp", "${classpath}"] },
	libraries: [
		{ name: "org.ow2.asm:asm:9.6", downloads: { artifact: { path: "org/ow2/asm/asm/9.6/asm-9.6.jar", url: "https://libraries.minecraft.net/asm-9.6.jar", sha1: "c" } } },
		{
			name: "org.lwjgl:lwjgl:3.3.3:natives-windows",
			downloads: { artifact: { path: "org/lwjgl/lwjgl/3.3.3/lwjgl-3.3.3-natives-windows.jar", url: "https://libraries.minecraft.net/lwjgl-natives.jar", sha1: "d" } },
			rules: [{ action: "allow", os: { name: "windows" } }],
		},
		{
			name: "org.lwjgl.lwjgl:lwjgl-platform:2.9.4",
			natives: { windows: "natives-windows-${arch}", linux: "natives-linux" },
			downloads: { classifiers: { "natives-windows-64": { path: "old/natives-64.jar", url: "https://libraries.minecraft.net/old-natives.jar", sha1: "e" } } },
		},
	],
}

const fabric: VersionJson = {
	id: "fabric-loader-0.16.9-1.21.1",
	inheritsFrom: "1.21.1",
	mainClass: "net.fabricmc.loader.impl.launch.knot.KnotClient",
	arguments: { game: [], jvm: ["-DFabricMcEmu= net.minecraft.client.main.Main "] },
	libraries: [
		{ name: "org.ow2.asm:asm:9.7.1", url: "https://maven.fabricmc.net/" },
		{ name: "net.fabricmc:fabric-loader:0.16.9", url: "https://maven.fabricmc.net/" },
	],
}

describe("version merging", () => {
	const merged = mergeVersions(vanilla, fabric)

	it("takes the loader main class and keeps vanilla downloads", () => {
		expect(merged.mainClass).toBe("net.fabricmc.loader.impl.launch.knot.KnotClient")
		expect(merged.downloads?.client?.url).toBe("https://example/client.jar")
		expect(merged.javaVersion?.component).toBe("java-runtime-delta")
	})

	it("lets the loader replace duplicate libraries", () => {
		const asm = merged.libraries.filter((library) => library.name.startsWith("org.ow2.asm:asm:"))
		expect(asm.map((library) => library.name)).toEqual(["org.ow2.asm:asm:9.7.1"])
	})

	it("joins arguments", () => {
		expect(merged.arguments?.jvm).toEqual(["-cp", "${classpath}", "-DFabricMcEmu= net.minecraft.client.main.Main "])
	})
})

describe("library resolution", () => {
	it("resolves classpath jars, maven libraries and natives per platform", () => {
		const libraries = resolveLibraries(mergeVersions(vanilla, fabric).libraries, windows)
		expect(libraries.find((library) => library.path === "net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar")?.url).toBe("https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar")
		const modernNatives = libraries.find((library) => library.path.includes("natives-windows.jar"))
		expect(modernNatives).toMatchObject({ classpath: true, native: true })
		const legacyNatives = libraries.find((library) => library.path === "old/natives-64.jar")
		expect(legacyNatives).toMatchObject({ classpath: false, native: true })
	})

	it("skips libraries for other systems", () => {
		const libraries = resolveLibraries(vanilla.libraries, linux)
		expect(libraries.some((library) => library.path.includes("natives-windows"))).toBe(false)
	})
})
