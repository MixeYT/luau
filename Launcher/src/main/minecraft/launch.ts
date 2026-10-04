import { delimiter, join } from "node:path"
import type { GcPreset } from "@shared/types"
import { rulesAllow, type Argument, type Environment } from "./versions"
import type { InstalledVersion } from "./installer"

export const LAUNCHER_NAME = "mixe-launcher"
export const LAUNCHER_VERSION = "0.1.0"

export interface Profile {
	username: string
	uuid: string
	accessToken: string
	xuid?: string
}

export interface LaunchOptions {
	installed: InstalledVersion
	java: string
	profile: Profile
	gameDirectory: string
	librariesRoot: string
	assetsRoot: string
	memoryMb: number
	gcPreset: GcPreset
	width: number
	height: number
	extraJvmArgs: string[]
	environment: Environment
}

// G1 tuned for short client pauses, ZGC as the low latency option on Java 21+.
export const GC_FLAGS: Record<GcPreset, string[]> = {
	g1: [
		"-XX:+UseG1GC",
		"-XX:+UnlockExperimentalVMOptions",
		"-XX:G1NewSizePercent=20",
		"-XX:G1ReservePercent=20",
		"-XX:MaxGCPauseMillis=50",
		"-XX:G1HeapRegionSize=32M",
		"-XX:+ParallelRefProcEnabled",
		"-XX:+DisableExplicitGC",
	],
	zgc: ["-XX:+UseZGC", "-XX:+ZGenerational", "-XX:+DisableExplicitGC"],
}

function expand(arguments_: Argument[], environment: Environment): string[] {
	const result: string[] = []
	for (const argument of arguments_) {
		if (typeof argument === "string") {
			result.push(argument)
		} else if (rulesAllow(argument.rules, environment)) {
			result.push(...(Array.isArray(argument.value) ? argument.value : [argument.value]))
		}
	}
	return result
}

function substitute(values: string[], variables: Record<string, string>): string[] {
	return values.map((value) => value.replace(/\$\{([^}]+)\}/g, (match, key: string) => variables[key] ?? match))
}

export function buildClasspath(options: Pick<LaunchOptions, "installed" | "librariesRoot">): string {
	const jars = options.installed.libraries.filter((library) => library.classpath).map((library) => join(options.librariesRoot, library.path))
	return [...new Set(jars), options.installed.clientJar].join(delimiter)
}

export function buildLaunchArguments(options: LaunchOptions): string[] {
	const { installed, profile, environment } = options
	const version = installed.version
	const classpath = buildClasspath(options)
	const variables: Record<string, string> = {
		auth_player_name: profile.username,
		auth_uuid: profile.uuid.replace(/-/g, ""),
		auth_access_token: profile.accessToken,
		auth_session: `token:${profile.accessToken}:${profile.uuid.replace(/-/g, "")}`,
		auth_xuid: profile.xuid ?? "0",
		clientid: "0",
		user_type: "msa",
		user_properties: "{}",
		version_name: version.id,
		version_type: version.type ?? "release",
		game_directory: options.gameDirectory,
		assets_root: options.assetsRoot,
		game_assets: options.assetsRoot,
		assets_index_name: version.assetIndex?.id ?? version.assets ?? "legacy",
		natives_directory: installed.nativesDirectory,
		library_directory: options.librariesRoot,
		classpath_separator: delimiter,
		classpath,
		launcher_name: LAUNCHER_NAME,
		launcher_version: LAUNCHER_VERSION,
		resolution_width: String(options.width),
		resolution_height: String(options.height),
	}

	const jvm = [`-Xms${Math.min(1024, options.memoryMb)}M`, `-Xmx${options.memoryMb}M`, ...GC_FLAGS[options.gcPreset], ...options.extraJvmArgs]
	if (version.arguments?.jvm?.length) {
		jvm.push(...substitute(expand(version.arguments.jvm, environment), variables))
	} else {
		jvm.push(`-Djava.library.path=${installed.nativesDirectory}`, "-cp", classpath)
	}
	if (version.logging?.client && installed.loggingConfig) {
		jvm.push(version.logging.client.argument.replace("${path}", installed.loggingConfig))
	}

	const game = version.arguments?.game?.length
		? substitute(expand(version.arguments.game, environment), variables)
		: substitute((version.minecraftArguments ?? "").split(" ").filter(Boolean), variables)
	if (!version.arguments?.game?.length) {
		game.push("--width", String(options.width), "--height", String(options.height))
	}

	return [...jvm, version.mainClass, ...game]
}
