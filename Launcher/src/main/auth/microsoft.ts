import type { DeviceCodePrompt } from "@shared/types"

// Azure app registration (Personal Microsoft accounts, public client flows enabled).
// New client ids also need Minecraft API access approved by Mojang, see docs/PROJEKT.md.
export const MICROSOFT_CLIENT_ID = process.env.MIXE_CLIENT_ID ?? "00000000-0000-0000-0000-000000000000"

const AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
const SCOPE = "XboxLive.signin offline_access"
const XBOX_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
const XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
const MINECRAFT_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
const ENTITLEMENTS_URL = "https://api.minecraftservices.com/entitlements/mcstore"
const PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"

const XSTS_ERRORS: Record<number, string> = {
	2148916233: "To konto Microsoft nie ma konta Xbox. Zaloguj się raz na xbox.com i spróbuj ponownie.",
	2148916235: "Xbox Live nie jest dostępny w Twoim kraju.",
	2148916236: "Konto wymaga weryfikacji wieku na xbox.com.",
	2148916237: "Konto wymaga weryfikacji wieku na xbox.com.",
	2148916238: "Konto dziecka musi zostać dodane do rodziny przez dorosłego.",
}

export interface StoredAccount {
	id: string
	username: string
	uuid: string
	xuid?: string
	refreshToken: string
	accessToken: string
	expiresAt: number
}

interface MicrosoftTokens {
	access_token: string
	refresh_token: string
	expires_in: number
}

type FetchLike = typeof fetch

export class MicrosoftAuth {
	constructor(
		private readonly clientId: string = MICROSOFT_CLIENT_ID,
		private readonly fetchImpl: FetchLike = fetch,
		private readonly sleep: (ms: number) => Promise<void> = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
	) {}

	private async form<T>(url: string, body: Record<string, string>): Promise<{ status: number; data: T }> {
		const response = await this.fetchImpl(url, {
			method: "POST",
			headers: { "Content-Type": "application/x-www-form-urlencoded" },
			body: new URLSearchParams(body).toString(),
		})
		return { status: response.status, data: (await response.json()) as T }
	}

	private async json<T>(url: string, body: unknown, bearer?: string): Promise<T> {
		const response = await this.fetchImpl(url, {
			method: body === undefined ? "GET" : "POST",
			headers: {
				Accept: "application/json",
				...(body === undefined ? {} : { "Content-Type": "application/json" }),
				...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
			},
			body: body === undefined ? undefined : JSON.stringify(body),
		})
		const text = await response.text()
		const data = text ? JSON.parse(text) : {}
		if (!response.ok) {
			const xboxError = XSTS_ERRORS[data.XErr as number]
			throw new Error(xboxError ?? `${url} failed with ${response.status}: ${text}`)
		}
		return data as T
	}

	// Shows a short code the user types at microsoft.com/link, no redirect server needed.
	async loginWithDeviceCode(onPrompt: (prompt: DeviceCodePrompt) => void): Promise<StoredAccount> {
		const { data: device } = await this.form<{ device_code: string; user_code: string; verification_uri: string; expires_in: number; interval: number }>(`${AUTHORITY}/devicecode`, {
			client_id: this.clientId,
			scope: SCOPE,
		})
		onPrompt({ userCode: device.user_code, verificationUri: device.verification_uri, expiresIn: device.expires_in })

		let interval = device.interval * 1000
		const deadline = Date.now() + device.expires_in * 1000
		while (Date.now() < deadline) {
			await this.sleep(interval)
			const { data } = await this.form<MicrosoftTokens & { error?: string }>(`${AUTHORITY}/token`, {
				grant_type: "urn:ietf:params:oauth:grant-type:device_code",
				client_id: this.clientId,
				device_code: device.device_code,
			})
			if (!data.error) {
				return this.loginWithMicrosoftToken(data)
			}
			if (data.error === "slow_down") {
				interval += 5000
			} else if (data.error !== "authorization_pending") {
				throw new Error(`Logowanie przerwane: ${data.error}`)
			}
		}
		throw new Error("Kod logowania wygasł, spróbuj jeszcze raz.")
	}

	async refresh(account: StoredAccount): Promise<StoredAccount> {
		if (account.expiresAt - Date.now() > 5 * 60 * 1000) {
			return account
		}
		const { status, data } = await this.form<MicrosoftTokens & { error?: string }>(`${AUTHORITY}/token`, {
			grant_type: "refresh_token",
			client_id: this.clientId,
			refresh_token: account.refreshToken,
			scope: SCOPE,
		})
		if (status !== 200 || data.error) {
			throw new Error("Sesja wygasła, zaloguj się ponownie.")
		}
		return this.loginWithMicrosoftToken(data)
	}

	private async loginWithMicrosoftToken(tokens: MicrosoftTokens): Promise<StoredAccount> {
		const xbox = await this.json<{ Token: string; DisplayClaims: { xui: { uhs: string }[] } }>(XBOX_AUTH_URL, {
			Properties: { AuthMethod: "RPS", SiteName: "user.auth.xboxlive.com", RpsTicket: `d=${tokens.access_token}` },
			RelyingParty: "http://auth.xboxlive.com",
			TokenType: "JWT",
		})
		const xsts = await this.json<{ Token: string; DisplayClaims: { xui: { uhs: string; xid?: string }[] } }>(XSTS_URL, {
			Properties: { SandboxId: "RETAIL", UserTokens: [xbox.Token] },
			RelyingParty: "rp://api.minecraftservices.com/",
			TokenType: "JWT",
		})
		const userHash = xsts.DisplayClaims.xui[0].uhs
		const minecraft = await this.json<{ access_token: string; expires_in: number }>(MINECRAFT_LOGIN_URL, {
			identityToken: `XBL3.0 x=${userHash};${xsts.Token}`,
		})
		const entitlements = await this.json<{ items: { name: string }[] }>(ENTITLEMENTS_URL, undefined, minecraft.access_token)
		if (!entitlements.items?.length) {
			throw new Error("To konto nie ma kupionego Minecraft: Java Edition.")
		}
		const profile = await this.json<{ id: string; name: string }>(PROFILE_URL, undefined, minecraft.access_token)
		return {
			id: profile.id,
			username: profile.name,
			uuid: profile.id,
			xuid: xsts.DisplayClaims.xui[0].xid,
			refreshToken: tokens.refresh_token,
			accessToken: minecraft.access_token,
			expiresAt: Date.now() + minecraft.expires_in * 1000,
		}
	}
}
