// Кошелёк USDC (ERC-20). Статус тянется один раз на сессию: Главной он нужен
// только чтобы решить, показывать ли переворот баланса в шапке. Баланс на бэкенде
// обновляет фоновый воркер раз в 5 минут, поэтому кэша тут достаточно.

import { writable, get } from 'svelte/store'
import { api, type WalletStatus } from './api'

export const wallet = writable<WalletStatus | null>(null)

let inflight: Promise<void> | null = null

/** `force` — дёрнуть Etherscan прямо сейчас, а не читать кэш бэкенда. */
export function loadWallet(force = false): Promise<void> {
  if (inflight) return inflight
  inflight = (force ? api.refreshWallet() : api.wallet())
    .then((s) => wallet.set(s))
    // Фича необязательная: без ключа/адреса просто молчим и не ломаем экран.
    .catch(() => {})
    .finally(() => { inflight = null })
  return inflight
}

let loadedOnce = false

/** Первая загрузка на сессию — Главная монтируется при каждом возврате на неё. */
export function loadWalletOnce(): Promise<void> {
  if (loadedOnce) return Promise.resolve()
  loadedOnce = true
  return loadWallet()
}

const STALE_MS = 60_000

/** Обновить, если кэш старше минуты — чтобы переворот не дёргал API вхолостую. */
export function refreshIfStale(): Promise<void> {
  const s = get(wallet)
  if (!s?.configured) return Promise.resolve()
  const checked = s.checked_at ? new Date(s.checked_at).getTime() : 0
  if (Number.isFinite(checked) && Date.now() - checked < STALE_MS) return Promise.resolve()
  return loadWallet(true)
}
