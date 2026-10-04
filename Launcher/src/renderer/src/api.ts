import type { LauncherApi } from "@shared/types"

declare global {
	interface Window {
		launcher: LauncherApi
	}
}

export const launcher = window.launcher

export function errorMessage(error: unknown): string {
	const message = error instanceof Error ? error.message : String(error)
	return message.replace(/^Error invoking remote method '[^']+': (Error: )?/, "")
}
