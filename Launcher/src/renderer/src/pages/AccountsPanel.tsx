import { useState } from "react"
import type { AccountSummary, DeviceCodePrompt } from "@shared/types"
import { launcher } from "../api"

interface Props {
	accounts: AccountSummary[]
	deviceCode?: DeviceCodePrompt
	onClose: () => void
	onChanged: () => Promise<void>
	run: (action: () => Promise<unknown>) => Promise<void>
}

export function AccountsPanel({ accounts, deviceCode, onClose, onChanged, run }: Props) {
	const [signingIn, setSigningIn] = useState(false)

	const addAccount = async () => {
		setSigningIn(true)
		await run(async () => {
			await launcher.addAccount()
			await onChanged()
		})
		setSigningIn(false)
	}

	return (
		<div className="modal-backdrop" onClick={onClose}>
			<div className="modal" onClick={(event) => event.stopPropagation()}>
				<h2>Konta Microsoft</h2>
				<div className="list">
					{accounts.map((account) => (
						<div key={account.id} className={account.selected ? "list-row selected" : "list-row"}>
							<img className="mod-icon" src={`https://mc-heads.net/avatar/${account.uuid}/40`} alt="" />
							<div className="grow">
								<div className="title">{account.username}</div>
								<div className="muted small">{account.selected ? "Aktywne" : "Kliknij, aby wybrać"}</div>
							</div>
							{!account.selected && (
								<button className="ghost small" onClick={() => run(async () => (await launcher.selectAccount(account.id), await onChanged()))}>
									Wybierz
								</button>
							)}
							<button className="danger small" onClick={() => run(async () => (await launcher.removeAccount(account.id), await onChanged()))}>
								Wyloguj
							</button>
						</div>
					))}
				</div>

				{signingIn && deviceCode && (
					<div className="device-code">
						<p>Otwórz <strong>{deviceCode.verificationUri}</strong> i wpisz kod:</p>
						<div className="code" onClick={() => navigator.clipboard.writeText(deviceCode.userCode)}>
							{deviceCode.userCode}
						</div>
						<p className="muted small">Kliknij kod, żeby go skopiować. Czekam na zalogowanie...</p>
					</div>
				)}

				<div className="row end">
					<button className="ghost" onClick={onClose}>
						Zamknij
					</button>
					<button className="primary" disabled={signingIn} onClick={addAccount}>
						{signingIn ? "Logowanie..." : "+ Dodaj konto Microsoft"}
					</button>
				</div>
			</div>
		</div>
	)
}
