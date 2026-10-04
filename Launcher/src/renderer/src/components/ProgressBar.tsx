import type { ProgressEvent } from "@shared/types"

export function ProgressBar({ progress }: { progress?: ProgressEvent }) {
	if (!progress) {
		return null
	}
	const percent = progress.total ? Math.round((progress.done / progress.total) * 100) : 0
	return (
		<div className="progress">
			<div className="progress-label">
				<span>{progress.task}</span>
				<span>{progress.total > 1 ? `${progress.done} / ${progress.total}` : `${percent}%`}</span>
			</div>
			<div className="progress-track">
				<div className="progress-fill" style={{ width: `${percent}%` }} />
			</div>
		</div>
	)
}
