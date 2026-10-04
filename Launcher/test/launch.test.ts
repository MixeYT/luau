import { delimiter, join } from "node:path"
import { describe, expect, it } from "vitest"
import type { InstalledVersion } from "../src/main/minecraft/installer"
import { buildLaunchArguments, type LaunchOptions } from "../src/main/minecraft/launch"
import type { Environment } from "../src/main/minecraft/versions"

const environment: Environment = { os: "windows", arch: "x64", osVersion: "10.0", features: { has_custom_resolution: true, is_demo_user: false } }

function options(installed: InstalledVersion): LaunchOptions {
	return {
		installed,
		java: "java",
		profile: { username: "MixeYT", uuid: "1234-abcd", accessToken: "token", xuid: "42" },
		gameDirectory: "/game",
		librariesRoot: "/libs",
		assetsRoot: "/assets",
		memoryMb: 4096,
		gcPreset: "g1",
		width: 1280,
		height: 720,
		extraJvmArgs: ["-Dtest=1"],
		environment,
	}
}

const modern: InstalledVersion = {
	clientJar: "/versions/1.21.1/1.21.1.jar",
	nativesDirectory: "/versions/1.21.1/natives",
	libraries: [
		{ path: "a/a.jar", url: "", classpath: true, native: false, exclude: [] },
		{ path: "old/natives.jar", url: "", classpath: false, native: true, exclude: [] },
	],
	version: {
		id: "1.21.1",
		type: "release",
		mainClass: "net.minecraft.client.main.Main",
		assetIndex: { id: "17", url: "", sha1: "", size: 0 },
		libraries: [],
		arguments: {
			game: [
				"--username",
				"${auth_player_name}",
				"--uuid",
				"${auth_uuid}",
				"--assetIndex",
				"${assets_index_name}",
				{ rules: [{ action: "allow", features: { is_demo_user: true } }], value: "--demo" },
				{ rules: [{ action: "allow", features: { has_custom_resolution: true } }], value: ["--width", "${resolution_width}", "--height", "${resolution_height}"] },
			],
			jvm: ["-Djava.library.path=${natives_directory}", "-cp", "${classpath}"],
		},
	},
}

describe("launch arguments", () => {
	it("builds modern arguments with rules and placeholders", () => {
		const args = buildLaunchArguments(options(modern))
		expect(args.slice(0, 2)).toEqual(["-Xms1024M", "-Xmx4096M"])
		expect(args).toContain("-XX:+UseG1GC")
		expect(args).toContain("-Dtest=1")
		expect(args).toContain("-Djava.library.path=/versions/1.21.1/natives")
		expect(args[args.indexOf("-cp") + 1]).toBe([join("/libs", "a/a.jar"), "/versions/1.21.1/1.21.1.jar"].join(delimiter))
		const game = args.slice(args.indexOf("net.minecraft.client.main.Main") + 1)
		expect(game).toEqual(["--username", "MixeYT", "--uuid", "1234abcd", "--assetIndex", "17", "--width", "1280", "--height", "720"])
		expect(game).not.toContain("--demo")
	})

	it("supports legacy minecraftArguments", () => {
		const legacy: InstalledVersion = {
			...modern,
			version: { ...modern.version, arguments: undefined, minecraftArguments: "--username ${auth_player_name} --accessToken ${auth_access_token} --userType ${user_type}" },
		}
		const args = buildLaunchArguments({ ...options(legacy), gcPreset: "zgc" })
		expect(args).toContain("-XX:+UseZGC")
		expect(args).toContain("-cp")
		const game = args.slice(args.indexOf("net.minecraft.client.main.Main") + 1)
		expect(game).toEqual(["--username", "MixeYT", "--accessToken", "token", "--userType", "msa", "--width", "1280", "--height", "720"])
	})
})
