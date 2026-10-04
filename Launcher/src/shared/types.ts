export type Loader = "vanilla" | "fabric"

export interface Instance {
	id: string
	name: string
	gameVersion: string
	loader: Loader
	loaderVersion?: string
	icon?: string
	memoryMb?: number
	created: number
	lastPlayed?: number
}

export interface InstanceDraft {
	name: string
	gameVersion: string
	loader: Loader
	optimize: boolean
}

export interface AccountSummary {
	id: string
	username: string
	uuid: string
	selected: boolean
}

export type GcPreset = "g1" | "zgc"

export interface Settings {
	memoryMb: number
	gcPreset: GcPreset
	windowWidth: number
	windowHeight: number
	closeOnLaunch: boolean
	extraJvmArgs: string
}

export interface InstalledMod {
	fileName: string
	enabled: boolean
	sizeBytes: number
}

export interface ModSearchHit {
	projectId: string
	slug: string
	title: string
	description: string
	iconUrl?: string
	downloads: number
	author: string
}

export interface GameVersion {
	id: string
	type: "release" | "snapshot" | "old_beta" | "old_alpha"
}

export interface DeviceCodePrompt {
	userCode: string
	verificationUri: string
	expiresIn: number
}

export interface ProgressEvent {
	task: string
	done: number
	total: number
}

export interface LogLine {
	instanceId: string
	line: string
	stream: "stdout" | "stderr" | "launcher"
}

export interface OptimizeReport {
	installed: string[]
	skipped: string[]
}

export interface LauncherApi {
	getVersions(): Promise<GameVersion[]>
	getSettings(): Promise<Settings>
	saveSettings(settings: Settings): Promise<void>

	listInstances(): Promise<Instance[]>
	createInstance(draft: InstanceDraft): Promise<Instance>
	deleteInstance(id: string): Promise<void>
	openInstanceFolder(id: string): Promise<void>
	launchInstance(id: string): Promise<void>

	listMods(instanceId: string): Promise<InstalledMod[]>
	setModEnabled(instanceId: string, fileName: string, enabled: boolean): Promise<void>
	deleteMod(instanceId: string, fileName: string): Promise<void>
	searchMods(instanceId: string, query: string): Promise<ModSearchHit[]>
	installMod(instanceId: string, projectId: string): Promise<string[]>
	applyOptimization(instanceId: string): Promise<OptimizeReport>

	exportModpack(instanceId: string): Promise<string | null>
	importModpack(): Promise<Instance | null>

	listAccounts(): Promise<AccountSummary[]>
	addAccount(): Promise<AccountSummary>
	selectAccount(id: string): Promise<void>
	removeAccount(id: string): Promise<void>

	onDeviceCode(callback: (prompt: DeviceCodePrompt) => void): () => void
	onProgress(callback: (event: ProgressEvent) => void): () => void
	onLog(callback: (line: LogLine) => void): () => void
}
