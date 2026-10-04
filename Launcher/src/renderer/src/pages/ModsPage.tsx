import { useCallback, useEffect, useState } from "react"
import type { InstalledMod, Instance, ModSearchHit, OptimizeReport, ProgressEvent } from "@shared/types"
import { launcher } from "../api"
import { InstancePicker } from "../components/InstancePicker"
import { ProgressBar } from "../components/ProgressBar"

interface Props {
	instance?: Instance
	instances: Instance[]
	onSelect: (id: string) => void
	run: (action: () => Promise<unknown>) => Promise<void>
	progress?: ProgressEvent
}

function formatSize(bytes: number): string {
	return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`
}

function formatDownloads(downloads: number): string {
	return downloads > 1_000_000 ? `${(downloads / 1_000_000).toFixed(1)}M` : downloads > 1000 ? `${Math.round(downloads / 1000)}k` : String(downloads)
}

export function ModsPage({ instance, instances, onSelect, run, progress }: Props) {
	const [mods, setMods] = useState<InstalledMod[]>([])
	const [query, setQuery] = useState("")
	const [results, setResults] = useState<ModSearchHit[]>([])
	const [busy, setBusy] = useState<string>()
	const [report, setReport] = useState<OptimizeReport>()
	const [notice, setNotice] = useState<string>()

	const refresh = useCallback(async () => {
		if (instance) {
			setMods(await launcher.listMods(instance.id))
		}
	}, [instance])

	useEffect(() => {
		setResults([])
		setReport(undefined)
		void run(refresh)
	}, [refresh, run])

	if (!instance) {
		return <p className="muted">Najpierw stwórz instancję.</p>
	}
	const isFabric = instance.loader === "fabric"

	const withBusy = async (key: string, action: () => Promise<unknown>) => {
		setBusy(key)
		setNotice(undefined)
		await run(action)
		setBusy(undefined)
	}

	return (
		<section>
			<div className="page-header">
				<div>
					<h1>Mody i modpacki</h1>
					<p className="muted">Mody pobierane z Modrinth razem z zależnościami.</p>
				</div>
				<InstancePicker instances={instances} selectedId={instance.id} onSelect={onSelect} />
			</div>

			<div className="actions-bar">
				<button
					className="primary"
					disabled={!isFabric || Boolean(busy)}
					onClick={() =>
						withBusy("optimize", async () => {
							setReport(await launcher.applyOptimization(instance.id))
							await refresh()
						})
					}
				>
					⚡ Pakiet optymalizacyjny
				</button>
				<button
					className="ghost"
					disabled={Boolean(busy)}
					onClick={() =>
						withBusy("export", async () => {
							const path = await launcher.exportModpack(instance.id)
							if (path) {
								setNotice(`Zapisano modpack: ${path}`)
							}
						})
					}
				>
					Eksportuj jako .mrpack
				</button>
				{!isFabric && <span className="muted">Mody działają tylko w instancjach Fabric.</span>}
			</div>
			{busy && <ProgressBar progress={progress} />}
			{notice && <div className="toast success">{notice}</div>}
			{report && (
				<div className="toast success">
					Zainstalowano {report.installed.length} modów.
					{report.skipped.length > 0 && ` Brak wersji dla: ${report.skipped.join(", ")}.`}
				</div>
			)}

			<div className="columns">
				<div className="panel">
					<div className="panel-header">
						<h2>Zainstalowane ({mods.length})</h2>
					</div>
					<div className="list">
						{mods.map((mod) => (
							<div key={mod.fileName} className={mod.enabled ? "list-row" : "list-row disabled"}>
								<label className="switch">
									<input type="checkbox" checked={mod.enabled} onChange={(event) => run(async () => (await launcher.setModEnabled(instance.id, mod.fileName, event.target.checked), await refresh()))} />
									<span />
								</label>
								<div className="grow">
									<div className="title">{mod.fileName.replace(/\.jar$/, "")}</div>
									<div className="muted small">{formatSize(mod.sizeBytes)}</div>
								</div>
								<button className="danger small" onClick={() => run(async () => (await launcher.deleteMod(instance.id, mod.fileName), await refresh()))}>
									✕
								</button>
							</div>
						))}
						{mods.length === 0 && <p className="muted">Brak modów. Dodaj pakiet optymalizacyjny albo poszukaj modów obok.</p>}
					</div>
				</div>

				<div className="panel">
					<form
						className="search"
						onSubmit={(event) => {
							event.preventDefault()
							void withBusy("search", async () => setResults(await launcher.searchMods(instance.id, query)))
						}}
					>
						<input className="input" disabled={!isFabric} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Szukaj na Modrinth, np. Iris, Xaero, AppleSkin" />
						<button className="primary" disabled={!isFabric || Boolean(busy)}>
							Szukaj
						</button>
					</form>
					<div className="list">
						{results.map((hit) => (
							<div key={hit.projectId} className="list-row">
								{hit.iconUrl ? <img className="mod-icon" src={hit.iconUrl} alt="" /> : <div className="mod-icon" />}
								<div className="grow">
									<div className="title">
										{hit.title} <span className="muted small">od {hit.author}</span>
									</div>
									<div className="muted small clamp">{hit.description}</div>
									<div className="muted small">⬇ {formatDownloads(hit.downloads)}</div>
								</div>
								<button
									className="primary small"
									disabled={Boolean(busy)}
									onClick={() =>
										withBusy(hit.projectId, async () => {
											const installed = await launcher.installMod(instance.id, hit.projectId)
											setNotice(`Zainstalowano: ${installed.join(", ")}`)
											await refresh()
										})
									}
								>
									{busy === hit.projectId ? "..." : "Dodaj"}
								</button>
							</div>
						))}
					</div>
				</div>
			</div>
		</section>
	)
}
