import { useEffect, useState } from "react"
import type { Settings } from "@shared/types"
import { launcher } from "../api"

export function SettingsPage({ run }: { run: (action: () => Promise<unknown>) => Promise<void> }) {
	const [settings, setSettings] = useState<Settings>()
	const [saved, setSaved] = useState(false)

	useEffect(() => {
		void run(async () => setSettings(await launcher.getSettings()))
	}, [run])

	if (!settings) {
		return null
	}
	const update = (changes: Partial<Settings>) => {
		setSettings({ ...settings, ...changes })
		setSaved(false)
	}

	return (
		<section className="settings">
			<h1>Ustawienia</h1>

			<div className="panel">
				<h2>Pamięć RAM</h2>
				<p className="muted">Dla modpacków z optymalizacją wystarczy 4–6 GB. Za dużo RAM wydłuża przerwy GC.</p>
				<div className="slider-row">
					<input type="range" min={1024} max={16384} step={512} value={settings.memoryMb} onChange={(event) => update({ memoryMb: Number(event.target.value) })} />
					<strong>{(settings.memoryMb / 1024).toFixed(1)} GB</strong>
				</div>
			</div>

			<div className="panel">
				<h2>Garbage collector</h2>
				<div className="segmented">
					<button className={settings.gcPreset === "g1" ? "active" : ""} onClick={() => update({ gcPreset: "g1" })}>
						G1 (stabilny)
					</button>
					<button className={settings.gcPreset === "zgc" ? "active" : ""} onClick={() => update({ gcPreset: "zgc" })}>
						ZGC (Java 21+, mniej lagów)
					</button>
				</div>
				<label>
					Dodatkowe argumenty JVM
					<input className="input" value={settings.extraJvmArgs} onChange={(event) => update({ extraJvmArgs: event.target.value })} placeholder="-XX:+UseStringDeduplication" />
				</label>
			</div>

			<div className="panel">
				<h2>Okno gry</h2>
				<div className="row">
					<label>
						Szerokość
						<input className="input" type="number" value={settings.windowWidth} onChange={(event) => update({ windowWidth: Number(event.target.value) })} />
					</label>
					<label>
						Wysokość
						<input className="input" type="number" value={settings.windowHeight} onChange={(event) => update({ windowHeight: Number(event.target.value) })} />
					</label>
				</div>
				<label className="check">
					<input type="checkbox" checked={settings.closeOnLaunch} onChange={(event) => update({ closeOnLaunch: event.target.checked })} />
					Chowaj launcher podczas gry
				</label>
			</div>

			<div className="row end">
				{saved && <span className="muted">Zapisano</span>}
				<button className="primary" onClick={() => run(async () => (await launcher.saveSettings(settings), setSaved(true)))}>
					Zapisz
				</button>
			</div>
		</section>
	)
}
