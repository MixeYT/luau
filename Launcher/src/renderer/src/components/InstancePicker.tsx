import type { Instance } from "@shared/types"

export function InstancePicker({ instances, selectedId, onSelect }: { instances: Instance[]; selectedId?: string; onSelect: (id: string) => void }) {
	return (
		<select className="input" value={selectedId ?? ""} onChange={(event) => onSelect(event.target.value)}>
			{instances.map((instance) => (
				<option key={instance.id} value={instance.id}>
					{instance.name} · {instance.gameVersion} {instance.loader === "fabric" ? "Fabric" : "Vanilla"}
				</option>
			))}
		</select>
	)
}
