import { useEffect, useState } from "react"
import type { GameVersion, Instance, InstanceDraft, ProgressEvent } from "@shared/types"
import { launcher } from "../api"
import { ProgressBar } from "../components/ProgressBar"

interface Props {
	instances: Instance[]
	selectedId?: string
	onSelect: (id: string) => void
	onChanged: () => Promise<void>
	run: (action: () => Promise<unknown>) => Promise<void>
	progress?: ProgressEvent
}

const EMPTY_DRAFT: InstanceDraft = { name: "", gameVersion: "", loader: "fabric", optimize: true }

export function InstancesPage({ instances, selectedId, onSelect, onChanged, run, progress }: Props) {
	const [versions, setVersions] = useState<GameVersion[]>([])
	const [draft, setDraft] = useState<InstanceDraft>()
	const [busy, setBusy] = useState(false)

	useEffect(() => {
		void run(async () => setVersions(await launcher.getVersions()))
	}, [run])

	const openDraft = () => setDraft({ ...EMPTY_DRAFT, gameVersion: versions[0]?.id ?? "" })

	const create = async () => {
		if (!draft?.name || !draft.gameVersion) {
			return
		}
		setBusy(true)
		await run(async () => {
			const instance = await launcher.createInstance(draft)
			setDraft(undefined)
			await onChanged()
			onSelect(instance.id)
		})
		setBusy(false)
	}

	const importPack = async () => {
		setBusy(true)
		await run(async () => {
			const instance = await launcher.importModpack()
			if (instance) {
				await onChanged()
				onSelect(instance.id)
			}
		})
		setBusy(false)
	}

	return (
		<section>
			<div className="page-header">
				<div>
					<h1>Instancje</h1>
					<p className="muted">Każda instancja ma własne mody, konfigi i światy.</p>
				</div>
				<div className="row">
					<button className="ghost" disabled={busy} onClick={importPack}>
						Importuj .mrpack
					</button>
					<button className="primary" disabled={busy} onClick={openDraft}>
						+ Nowa instancja
					</button>
				</div>
			</div>
			{busy && <ProgressBar progress={progress} />}

			<div className="grid">
				{instances.map((instance) => (
					<article key={instance.id} className={instance.id === selectedId ? "card selected" : "card"} onClick={() => onSelect(instance.id)}>
						<div className="card-art">{instance.name.slice(0, 1).toUpperCase()}</div>
						<h3>{instance.name}</h3>
						<p className="muted">
							{instance.gameVersion} · {instance.loader === "fabric" ? `Fabric ${instance.loaderVersion ?? ""}` : "Vanilla"}
						</p>
						<div className="row">
							<button className="ghost small" onClick={(event) => (event.stopPropagation(), void launcher.openInstanceFolder(instance.id))}>
								Folder
							</button>
							<button
								className="danger small"
								onClick={(event) => {
									event.stopPropagation()
									if (confirm(`Usunąć instancję ${instance.name} razem ze światami?`)) {
										void run(async () => {
											await launcher.deleteInstance(instance.id)
											await onChanged()
										})
									}
								}}
							>
								Usuń
							</button>
						</div>
					</article>
				))}
				{instances.length === 0 && <p className="muted">Nie masz jeszcze instancji. Stwórz nową albo zaimportuj modpack .mrpack.</p>}
			</div>

			{draft && (
				<div className="modal-backdrop" onClick={() => !busy && setDraft(undefined)}>
					<div className="modal" onClick={(event) => event.stopPropagation()}>
						<h2>Nowa instancja</h2>
						<label>
							Nazwa
							<input className="input" value={draft.name} autoFocus onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="np. PvP 1.21" />
						</label>
						<label>
							Wersja Minecraft
							<select className="input" value={draft.gameVersion} onChange={(event) => setDraft({ ...draft, gameVersion: event.target.value })}>
								{versions.map((version) => (
									<option key={version.id}>{version.id}</option>
								))}
							</select>
						</label>
						<div className="segmented">
							{(["fabric", "vanilla"] as const).map((loader) => (
								<button key={loader} className={draft.loader === loader ? "active" : ""} onClick={() => setDraft({ ...draft, loader, optimize: loader === "fabric" && draft.optimize })}>
									{loader === "fabric" ? "Fabric" : "Vanilla"}
								</button>
							))}
						</div>
						<label className="check">
							<input type="checkbox" disabled={draft.loader !== "fabric"} checked={draft.optimize} onChange={(event) => setDraft({ ...draft, optimize: event.target.checked })} />
							Zainstaluj pakiet optymalizacyjny (Sodium, Lithium, FerriteCore, ModernFix...)
						</label>
						{busy && <ProgressBar progress={progress} />}
						<div className="row end">
							<button className="ghost" disabled={busy} onClick={() => setDraft(undefined)}>
								Anuluj
							</button>
							<button className="primary" disabled={busy || !draft.name} onClick={create}>
								{busy ? "Tworzenie..." : "Stwórz"}
							</button>
						</div>
					</div>
				</div>
			)}
		</section>
	)
}
