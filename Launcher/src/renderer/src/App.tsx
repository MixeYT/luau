import { useCallback, useEffect, useState } from "react"
import type { AccountSummary, DeviceCodePrompt, Instance, LogLine, ProgressEvent } from "@shared/types"
import { errorMessage, launcher } from "./api"
import { AccountsPanel } from "./pages/AccountsPanel"
import { HomePage } from "./pages/HomePage"
import { InstancesPage } from "./pages/InstancesPage"
import { ModsPage } from "./pages/ModsPage"
import { SettingsPage } from "./pages/SettingsPage"

type Page = "home" | "instances" | "mods" | "settings"

const NAVIGATION: { page: Page; label: string; icon: string }[] = [
	{ page: "home", label: "Graj", icon: "▶" },
	{ page: "instances", label: "Instancje", icon: "▦" },
	{ page: "mods", label: "Mody i modpacki", icon: "⬡" },
	{ page: "settings", label: "Ustawienia", icon: "⚙" },
]

export function App() {
	const [page, setPage] = useState<Page>("home")
	const [instances, setInstances] = useState<Instance[]>([])
	const [selectedId, setSelectedId] = useState<string>()
	const [accounts, setAccounts] = useState<AccountSummary[]>([])
	const [progress, setProgress] = useState<ProgressEvent>()
	const [logs, setLogs] = useState<LogLine[]>([])
	const [deviceCode, setDeviceCode] = useState<DeviceCodePrompt>()
	const [error, setError] = useState<string>()
	const [showAccounts, setShowAccounts] = useState(false)

	const refreshInstances = useCallback(async () => {
		const list = await launcher.listInstances()
		setInstances(list)
		setSelectedId((current) => (current && list.some((instance) => instance.id === current) ? current : list[0]?.id))
	}, [])

	const refreshAccounts = useCallback(async () => setAccounts(await launcher.listAccounts()), [])

	useEffect(() => {
		void refreshInstances()
		void refreshAccounts()
		const unsubscribe = [
			launcher.onProgress(setProgress),
			launcher.onLog((line) => setLogs((current) => [...current.slice(-500), line])),
			launcher.onDeviceCode(setDeviceCode),
		]
		return () => unsubscribe.forEach((stop) => stop())
	}, [refreshInstances, refreshAccounts])

	const run = useCallback(async (action: () => Promise<unknown>) => {
		setError(undefined)
		try {
			await action()
		} catch (caught) {
			setError(errorMessage(caught))
		}
	}, [])

	const selected = instances.find((instance) => instance.id === selectedId)
	const account = accounts.find((entry) => entry.selected) ?? accounts[0]

	return (
		<div className="shell">
			<aside className="sidebar">
				<div className="brand">
					<span className="brand-mark">M</span>
					<span>Mixe Launcher</span>
				</div>
				<nav>
					{NAVIGATION.map((entry) => (
						<button key={entry.page} className={page === entry.page ? "nav-item active" : "nav-item"} onClick={() => setPage(entry.page)}>
							<span className="nav-icon">{entry.icon}</span>
							{entry.label}
						</button>
					))}
				</nav>
				<button className="account-chip" onClick={() => setShowAccounts(true)}>
					{account ? <img src={`https://mc-heads.net/avatar/${account.uuid}/32`} alt="" /> : <span className="avatar-placeholder">?</span>}
					<span>{account ? account.username : "Zaloguj się"}</span>
				</button>
			</aside>

			<main className="content">
				{error && (
					<div className="toast error" onClick={() => setError(undefined)}>
						{error}
					</div>
				)}
				{page === "home" && <HomePage instance={selected} instances={instances} onSelect={setSelectedId} progress={progress} logs={logs.filter((line) => line.instanceId === selectedId)} run={run} hasAccount={Boolean(account)} onLogin={() => setShowAccounts(true)} />}
				{page === "instances" && <InstancesPage instances={instances} selectedId={selectedId} onSelect={setSelectedId} onChanged={refreshInstances} run={run} progress={progress} />}
				{page === "mods" && <ModsPage instance={selected} instances={instances} onSelect={setSelectedId} run={run} progress={progress} />}
				{page === "settings" && <SettingsPage run={run} />}
			</main>

			{showAccounts && (
				<AccountsPanel
					accounts={accounts}
					deviceCode={deviceCode}
					onClose={() => {
						setShowAccounts(false)
						setDeviceCode(undefined)
					}}
					onChanged={async () => {
						setDeviceCode(undefined)
						await refreshAccounts()
					}}
					run={run}
				/>
			)}
		</div>
	)
}
