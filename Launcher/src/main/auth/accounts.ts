import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname } from "node:path"
import type { AccountSummary } from "@shared/types"
import type { StoredAccount } from "./microsoft"

export interface Cipher {
	encrypt(text: string): Buffer
	decrypt(data: Buffer): string
}

interface AccountFile {
	selected?: string
	accounts: StoredAccount[]
}

// Tokens never touch the disk in plain text, the cipher comes from Electron safeStorage (DPAPI on Windows).
export class AccountStore {
	constructor(
		private readonly path: string,
		private readonly cipher: Cipher,
	) {}

	private async read(): Promise<AccountFile> {
		try {
			return JSON.parse(this.cipher.decrypt(await readFile(this.path))) as AccountFile
		} catch {
			return { accounts: [] }
		}
	}

	private async write(file: AccountFile): Promise<void> {
		await mkdir(dirname(this.path), { recursive: true })
		await writeFile(this.path, this.cipher.encrypt(JSON.stringify(file)))
	}

	async list(): Promise<AccountSummary[]> {
		const file = await this.read()
		return file.accounts.map((account) => ({ id: account.id, username: account.username, uuid: account.uuid, selected: account.id === file.selected }))
	}

	async selected(): Promise<StoredAccount | undefined> {
		const file = await this.read()
		return file.accounts.find((account) => account.id === file.selected) ?? file.accounts[0]
	}

	async save(account: StoredAccount, select = true): Promise<void> {
		const file = await this.read()
		file.accounts = [...file.accounts.filter((entry) => entry.id !== account.id), account]
		if (select || !file.selected) {
			file.selected = account.id
		}
		await this.write(file)
	}

	async select(id: string): Promise<void> {
		const file = await this.read()
		if (file.accounts.some((account) => account.id === id)) {
			file.selected = id
			await this.write(file)
		}
	}

	async remove(id: string): Promise<void> {
		const file = await this.read()
		file.accounts = file.accounts.filter((account) => account.id !== id)
		if (file.selected === id) {
			file.selected = file.accounts[0]?.id
		}
		await this.write(file)
	}
}
