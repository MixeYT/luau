import { mkdtemp } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import { AccountStore } from "../src/main/auth/accounts"
import { MicrosoftAuth } from "../src/main/auth/microsoft"

function jsonResponse(data: unknown, status = 200): Response {
	return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } })
}

function fakeMicrosoft(overrides: Record<string, () => Response> = {}) {
	let polls = 0
	const calls: string[] = []
	const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = String(input)
		calls.push(url)
		const body = String(init?.body ?? "")
		for (const [key, respond] of Object.entries(overrides)) {
			if (url.includes(key)) {
				return respond()
			}
		}
		if (url.endsWith("/devicecode")) {
			return jsonResponse({ device_code: "dev", user_code: "ABCD-1234", verification_uri: "https://microsoft.com/link", expires_in: 900, interval: 1 })
		}
		if (url.endsWith("/token")) {
			if (body.includes("device_code") && polls++ === 0) {
				return jsonResponse({ error: "authorization_pending" }, 400)
			}
			return jsonResponse({ access_token: "ms-access", refresh_token: "ms-refresh", expires_in: 3600 })
		}
		if (url.includes("user.auth.xboxlive.com")) {
			expect(JSON.parse(body).Properties.RpsTicket).toBe("d=ms-access")
			return jsonResponse({ Token: "xbl", DisplayClaims: { xui: [{ uhs: "hash" }] } })
		}
		if (url.includes("xsts.auth.xboxlive.com")) {
			return jsonResponse({ Token: "xsts", DisplayClaims: { xui: [{ uhs: "hash", xid: "2535" }] } })
		}
		if (url.includes("login_with_xbox")) {
			expect(JSON.parse(body).identityToken).toBe("XBL3.0 x=hash;xsts")
			return jsonResponse({ access_token: "mc-token", expires_in: 86400 })
		}
		if (url.includes("entitlements")) {
			return jsonResponse({ items: [{ name: "game_minecraft" }] })
		}
		if (url.includes("minecraft/profile")) {
			return jsonResponse({ id: "uuid-1", name: "MixeYT" })
		}
		throw new Error(`Unexpected request ${url}`)
	}) as typeof fetch
	return { fetchImpl, calls }
}

describe("microsoft login", () => {
	it("runs the device code flow through Xbox Live to a Minecraft profile", async () => {
		const { fetchImpl } = fakeMicrosoft()
		const prompts: string[] = []
		const auth = new MicrosoftAuth("client", fetchImpl, async () => undefined)
		const account = await auth.loginWithDeviceCode((prompt) => prompts.push(prompt.userCode))
		expect(prompts).toEqual(["ABCD-1234"])
		expect(account).toMatchObject({ username: "MixeYT", uuid: "uuid-1", xuid: "2535", accessToken: "mc-token", refreshToken: "ms-refresh" })
	})

	it("explains missing Xbox accounts", async () => {
		const { fetchImpl } = fakeMicrosoft({ "xsts.auth.xboxlive.com": () => jsonResponse({ XErr: 2148916233 }, 401) })
		const auth = new MicrosoftAuth("client", fetchImpl, async () => undefined)
		await expect(auth.loginWithDeviceCode(() => undefined)).rejects.toThrow(/nie ma konta Xbox/)
	})

	it("rejects accounts without the game", async () => {
		const { fetchImpl } = fakeMicrosoft({ entitlements: () => jsonResponse({ items: [] }) })
		const auth = new MicrosoftAuth("client", fetchImpl, async () => undefined)
		await expect(auth.loginWithDeviceCode(() => undefined)).rejects.toThrow(/Java Edition/)
	})

	it("only refreshes tokens that are about to expire", async () => {
		const { fetchImpl, calls } = fakeMicrosoft()
		const auth = new MicrosoftAuth("client", fetchImpl, async () => undefined)
		const fresh = { id: "uuid-1", username: "MixeYT", uuid: "uuid-1", refreshToken: "r", accessToken: "a", expiresAt: Date.now() + 3600_000 }
		expect(await auth.refresh(fresh)).toBe(fresh)
		expect(calls).toHaveLength(0)
		const refreshed = await auth.refresh({ ...fresh, expiresAt: Date.now() })
		expect(refreshed.accessToken).toBe("mc-token")
	})
})

describe("account store", () => {
	it("keeps tokens encrypted and tracks the selected account", async () => {
		const directory = await mkdtemp(join(tmpdir(), "mixe-accounts-"))
		const cipher = { encrypt: (text: string) => Buffer.from(text).reverse(), decrypt: (data: Buffer) => Buffer.from(data).reverse().toString() }
		const store = new AccountStore(join(directory, "accounts.dat"), cipher)
		await store.save({ id: "a", username: "First", uuid: "a", refreshToken: "secret-refresh", accessToken: "secret", expiresAt: 0 })
		await store.save({ id: "b", username: "Second", uuid: "b", refreshToken: "r", accessToken: "t", expiresAt: 0 })
		expect((await store.list()).map((account) => [account.username, account.selected])).toEqual([
			["First", false],
			["Second", true],
		])
		await store.select("a")
		expect((await store.selected())?.username).toBe("First")
		await store.remove("a")
		expect((await store.selected())?.username).toBe("Second")
	})
})
