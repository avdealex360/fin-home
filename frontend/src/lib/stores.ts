import { writable } from 'svelte/store'

// null = unknown yet (checking session), false = show login screen.
export const authenticated = writable<boolean | null>(null)

const now = new Date()
export const period = writable<{ year: number; month: number }>({
  year: now.getFullYear(),
  month: now.getMonth() + 1,
})

// Hash-based route, e.g. "#/plan" -> "plan". Default "dashboard".
function routeFromHash(): string {
  const h = window.location.hash.replace(/^#\/?/, '')
  return h || 'dashboard'
}
export const route = writable<string>(routeFromHash())
window.addEventListener('hashchange', () => route.set(routeFromHash()))
export function navigate(to: string) {
  window.location.hash = `/${to}`
}

// "Пояснения" — plain-language captions under every number. Persisted so the
// switch survives reloads; on by default for the first month of use.
const HELP_KEY = 'finhome.showHelp'
const helpStored = localStorage.getItem(HELP_KEY)
export const showHelp = writable<boolean>(helpStored === null ? true : helpStored === '1')
showHelp.subscribe((v) => localStorage.setItem(HELP_KEY, v ? '1' : '0'))

// Toast with optional undo action.
export interface ToastState {
  message: string
  undo?: () => void
  id: number
}
export const toast = writable<ToastState | null>(null)
let toastId = 0
let toastTimer: ReturnType<typeof setTimeout> | null = null
export function showToast(message: string, undo?: () => void) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.set({ message, undo, id: ++toastId })
  toastTimer = setTimeout(() => toast.set(null), 5000)
}

// A signal that bumps whenever data changes so screens can refetch.
export const dataVersion = writable(0)
export function invalidate() {
  dataVersion.update((n) => n + 1)
}
