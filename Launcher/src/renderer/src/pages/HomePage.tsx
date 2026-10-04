import { useEffect, useRef, useState } from "react"
import type { Instance, LogLine, ProgressEvent } from "@shared/types"
import { launcher } from "../api"
import { InstancePicker } from "../components/InstancePicker"
import { ProgressBar } from "../components/ProgressBar"

interface Props {
	instance?: Instance
	instances: Instance[]
	onSelect: (id: string) => void
	progress?: ProgressEvent
	logs: LogLine[]
	run: (action: () => Promise<unknown>) => Promise<void>
	hasAccount: boolean
	onLogin: () => void
}

export function HomePage({ instance, instances, onSelect, progress, logs, run, hasAccount, onLogin }: Props) {
	const [launching, setLaunching] = useState(false)
	const [showLog, setShowLog] = useState(false)
	const logEnd = useRef<HTMLDivElement>(null)

	useEffect(() => logEnd.current?.scrollIntoView({ block: "end" }), [logs.length, showLog])

	const play = async () => {
		if (!instance) {
			return
		}
		setLaunching(true)
		await run(() => launcher.launchInstance(instance.id))
		setLaunching(false)
	}

	return (
		<section className="home">
			<div className="hero">
				<div className="hero-glow" />
				<p className="eyebrow">{instance ? `${instance.gameVersion} · ${instance.loader === "fabric" ? "Fabric" : "Vanilla"}` : "Brak instancji"}</p>
				<h1>{instance?.name ?? "Stwórz pierwszą instancję"}</h1>
				<p className="muted">Zoptymalizowany Minecraft z modami z Modrinth, Twoimi modpackami i logowaniem Microsoft.</p>
				<div className="hero-actions">
					{instances.length > 0 && <InstancePicker instances={instances} selectedId={instance?.id} onSelect={onSelect} />}
					{hasAccount ? (
						<button className="play-button" disabled={!instance || launching} onClick={play}>
							{launching ? "Uruchamianie..." : "GRAJ"}
						</button>
					) : (
						<button className="play-button" onClick={onLogin}>
							Zaloguj się
						</button>
					)}
				</div>
				<ProgressBar progress={launching ? progress : undefined} />
			</div>

			<div className="panel">
				<div className="panel-header">
					<h2>Konsola gry</h2>
					<button className="ghost" onClick={() => setShowLog(!showLog)}>
						{showLog ? "Ukryj" : "Pokaż"}
					</button>
				</div>
				{showLog && (
					<div className="console">
						{logs.length === 0 && <p className="muted">Tu pojawią się logi po uruchomieniu gry.</p>}
						{logs.map((line, index) => (
							<div key={index} className={`console-line ${line.stream}`}>
								{line.line}
							</div>
						))}
						<div ref={logEnd} />
					</div>
				)}
			</div>
		</section>
	)
}
